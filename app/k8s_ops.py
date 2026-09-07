import asyncio
import shlex
from datetime import datetime, timezone
from kubernetes import client, config as kube_config, watch
from kubernetes.client.rest import ApiException
from config import cfg

_core = None
_apps = None
_net = None


def init():
    global _core, _apps, _net
    try:
        kube_config.load_incluster_config()
    except kube_config.ConfigException:
        kube_config.load_kube_config()
    _core = client.CoreV1Api()
    _apps = client.AppsV1Api()
    _net = client.NetworkingV1Api()


def _age(dt):
    if not dt:
        return "?"
    seconds = int((datetime.now(timezone.utc) - dt).total_seconds())
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def _selector():
    dep = _apps.read_namespaced_deployment(cfg.TARGET_DEPLOYMENT, cfg.TARGET_NAMESPACE)
    labels = dep.spec.selector.match_labels or {}
    return ",".join(f"{k}={v}" for k, v in labels.items())


def deployment_state():
    try:
        dep = _apps.read_namespaced_deployment(cfg.TARGET_DEPLOYMENT, cfg.TARGET_NAMESPACE)
    except ApiException as exc:
        return {"error": f"Deployment {cfg.TARGET_NAMESPACE}/{cfg.TARGET_DEPLOYMENT} was not found ({exc.status})"}
    st = dep.status
    pods = _core.list_namespaced_pod(cfg.TARGET_NAMESPACE, label_selector=_selector()).items
    image = dep.spec.template.spec.containers[0].image if dep.spec.template.spec.containers else "-"
    desired = dep.spec.replicas or 0
    ready = st.ready_replicas or 0
    updated = st.updated_replicas or 0
    available = st.available_replicas or 0
    return {
        "name": dep.metadata.name,
        "namespace": cfg.TARGET_NAMESPACE,
        "image": image,
        "desired": desired,
        "ready": ready,
        "updated": updated,
        "available": available,
        "generation": dep.metadata.generation or 0,
        "observed_generation": st.observed_generation or 0,
        "rolling": not (ready == desired and updated == desired and available == desired),
        "max_replicas": cfg.MAX_REPLICAS,
        "pods": sorted([
            {
                "name": p.metadata.name,
                "phase": p.status.phase,
                "ready": all(c.ready for c in (p.status.container_statuses or [])) if p.status.container_statuses else False,
                "restarts": sum(c.restart_count for c in (p.status.container_statuses or [])),
                "node": p.spec.node_name or "-",
                "ip": p.status.pod_ip or "-",
                "age": _age(p.status.start_time),
                "terminating": p.metadata.deletion_timestamp is not None,
            }
            for p in pods
        ], key=lambda x: x["name"]),
    }


def kill_pod(name):
    valid = {p["name"] for p in deployment_state().get("pods", [])}
    if name not in valid:
        raise ValueError(f"Pod {name} does not belong to Deployment {cfg.TARGET_DEPLOYMENT}")
    _core.delete_namespaced_pod(name, cfg.TARGET_NAMESPACE)
    return f"Pod {name} marked for deletion"


def scale(replicas):
    if not 1 <= replicas <= cfg.MAX_REPLICAS:
        raise ValueError(f"Replica count must be between 1 and {cfg.MAX_REPLICAS}")
    _apps.patch_namespaced_deployment_scale(
        cfg.TARGET_DEPLOYMENT,
        cfg.TARGET_NAMESPACE,
        {"spec": {"replicas": replicas}},
    )
    return f"Replica count changed to {replicas}"


def restart(source="manual"):
    stamp = datetime.now(timezone.utc).isoformat()
    _apps.patch_namespaced_deployment(
        cfg.TARGET_DEPLOYMENT,
        cfg.TARGET_NAMESPACE,
        {"spec": {"template": {"metadata": {"annotations": {
            "kubectl.kubernetes.io/restartedAt": stamp,
            "migration-lab/demo-source": source,
        }}}}},
    )
    return "Rolling redeployment requested"


def _table(headers, rows):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(str(value)))
    fmt = "  ".join("{:<" + str(w) + "}" for w in widths)
    return "\n".join(
        [fmt.format(*headers), fmt.format(*["-" * w for w in widths])]
        + [fmt.format(*[str(v) for v in row]) for row in rows]
    )


def _pods(wide=False):
    ns = cfg.TARGET_NAMESPACE
    pods = _core.list_namespaced_pod(ns).items
    rows = []
    for p in pods:
        ready = sum(1 for c in (p.status.container_statuses or []) if c.ready)
        total = len(p.status.container_statuses or [])
        row = [p.metadata.name, f"{ready}/{total}", p.status.phase,
               sum(c.restart_count for c in (p.status.container_statuses or [])), _age(p.status.start_time)]
        if wide:
            row += [p.status.pod_ip or "-", p.spec.node_name or "-"]
        rows.append(row)
    headers = ["NAME", "READY", "STATUS", "RESTARTS", "AGE"] + (["IP", "NODE"] if wide else [])
    suffix = " -o wide" if wide else ""
    return f"$ kubectl get pods -n {ns}{suffix}\n" + _table(headers, rows)


def _nodes(wide=False):
    nodes = _core.list_node().items
    rows = []
    for n in nodes:
        conditions = {c.type: c.status for c in (n.status.conditions or [])}
        status = "Ready" if conditions.get("Ready") == "True" else "NotReady"
        addresses = {a.type: a.address for a in (n.status.addresses or [])}
        row = [n.metadata.name, status, _age(n.metadata.creation_timestamp), n.status.node_info.kubelet_version]
        if wide:
            row += [addresses.get("InternalIP", "-"), n.status.node_info.os_image, n.status.node_info.container_runtime_version]
        rows.append(row)
    headers = ["NAME", "STATUS", "AGE", "VERSION"] + (["INTERNAL-IP", "OS-IMAGE", "CONTAINER-RUNTIME"] if wide else [])
    suffix = " -o wide" if wide else ""
    return f"$ kubectl get nodes{suffix}\n" + _table(headers, rows)


def _deployments():
    ns = cfg.TARGET_NAMESPACE
    deployments = _apps.list_namespaced_deployment(ns).items
    rows = [[d.metadata.name, f"{d.status.ready_replicas or 0}/{d.spec.replicas or 0}", d.status.updated_replicas or 0,
             d.status.available_replicas or 0, _age(d.metadata.creation_timestamp)] for d in deployments]
    return f"$ kubectl get deployments -n {ns}\n" + _table(["NAME", "READY", "UP-TO-DATE", "AVAILABLE", "AGE"], rows)


def _services():
    ns = cfg.TARGET_NAMESPACE
    services = _core.list_namespaced_service(ns).items
    rows = []
    for s in services:
        ingress = s.status.load_balancer.ingress or []
        external = ",".join((getattr(i, "ip", None) or getattr(i, "hostname", None) or "-") for i in ingress) or "-"
        rows.append([s.metadata.name, s.spec.type, s.spec.cluster_ip or "-", external,
                     ",".join(f"{p.port}/{p.protocol}" for p in (s.spec.ports or [])), _age(s.metadata.creation_timestamp)])
    return f"$ kubectl get services -n {ns}\n" + _table(["NAME", "TYPE", "CLUSTER-IP", "EXTERNAL-IP", "PORT(S)", "AGE"], rows)


def _ingress():
    ns = cfg.TARGET_NAMESPACE
    ingresses = _net.list_namespaced_ingress(ns).items
    rows = []
    for x in ingresses:
        lb = x.status.load_balancer.ingress or []
        address = ",".join((getattr(i, "ip", None) or getattr(i, "hostname", None) or "-") for i in lb) or "-"
        rows.append([x.metadata.name, x.spec.ingress_class_name or "-", ",".join(r.host or "*" for r in (x.spec.rules or [])) or "*", address, _age(x.metadata.creation_timestamp)])
    return f"$ kubectl get ingress -n {ns}\n" + _table(["NAME", "CLASS", "HOSTS", "ADDRESS", "AGE"], rows)


def _events():
    ns = cfg.TARGET_NAMESPACE
    events = sorted(
        _core.list_namespaced_event(ns).items,
        key=lambda e: e.last_timestamp or e.event_time or e.metadata.creation_timestamp or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[:25]
    rows = [[e.type or "-", e.reason or "-", e.involved_object.kind + "/" + e.involved_object.name, (e.message or "")[:90]] for e in events]
    return f"$ kubectl get events -n {ns} --sort-by=.lastTimestamp\n" + _table(["TYPE", "REASON", "OBJECT", "MESSAGE"], rows)


def _describe_pod(name):
    ns = cfg.TARGET_NAMESPACE
    try:
        p = _core.read_namespaced_pod(name, ns)
    except ApiException as exc:
        raise ValueError(f"Pod {name} not found ({exc.status})")
    conditions = "\n".join(f"  {c.type}: {c.status} ({c.reason or '-'})" for c in (p.status.conditions or [])) or "  -"
    containers = "\n".join(
        f"  {c.name}: image={c.image}, ready={c.ready}, restarts={c.restart_count}"
        for c in (p.status.container_statuses or [])
    ) or "  -"
    return (
        f"$ kubectl describe pod {name} -n {ns}\n"
        f"Name:       {p.metadata.name}\nNamespace:  {ns}\nNode:       {p.spec.node_name or '-'}\n"
        f"IP:         {p.status.pod_ip or '-'}\nPhase:      {p.status.phase}\nAge:        {_age(p.status.start_time)}\n"
        f"Containers:\n{containers}\nConditions:\n{conditions}"
    )


def _api_resources():
    return "$ kubectl api-resources\nNAME          APIVERSION             NAMESPACED\npods          v1                     true\nservices      v1                     true\nnodes         v1                     false\ndeployments   apps/v1                true\ningresses     networking.k8s.io/v1   true"


def _version():
    v = _core.get_code().to_dict() if hasattr(_core, "get_code") else {}
    return "$ kubectl version\nServer: Kubernetes API reachable\nClient: browser-safe command console"


def _cluster_info():
    return "$ kubectl cluster-info\nKubernetes control plane: reachable through in-cluster ServiceAccount\nNamespace: " + cfg.TARGET_NAMESPACE


def parse_readonly_command(text: str):
    """Parse a small kubectl-like read-only whitelist. No shell is executed."""
    try:
        t = shlex.split(text.strip())
    except ValueError as exc:
        raise ValueError(f"Invalid command syntax: {exc}")
    if not t:
        raise ValueError("Enter a command.")
    if t[0] == "$":
        t = t[1:]
    if not t or t[0] != "kubectl":
        raise ValueError("Only approved read-only kubectl commands are available.")

    # Strip the only namespace forms we permit. The console is pinned to prod.
    clean = []
    i = 1
    while i < len(t):
        if t[i] in ("-n", "--namespace"):
            if i + 1 >= len(t) or t[i + 1] != cfg.TARGET_NAMESPACE:
                raise ValueError(f"Only namespace '{cfg.TARGET_NAMESPACE}' is allowed.")
            i += 2
            continue
        clean.append(t[i])
        i += 1

    if clean == ["get", "pods"]:
        return _pods(False)
    if clean in (["get", "pods", "-o", "wide"], ["get", "pods", "--output", "wide"]):
        return _pods(True)
    if clean == ["get", "nodes"]:
        return _nodes(False)
    if clean in (["get", "nodes", "-o", "wide"], ["get", "nodes", "--output", "wide"]):
        return _nodes(True)
    if clean in (["get", "deployments"], ["get", "deployment"], ["get", "deploy"]):
        return _deployments()
    if clean in (["get", "services"], ["get", "service"], ["get", "svc"]):
        return _services()
    if clean in (["get", "ingress"], ["get", "ingresses"], ["get", "ing"]):
        return _ingress()
    if clean[:2] == ["get", "events"]:
        return _events()
    if len(clean) == 3 and clean[:2] == ["describe", "pod"]:
        return _describe_pod(clean[2])
    if clean == ["api-resources"]:
        return _api_resources()
    if clean == ["version"]:
        return _version()
    if clean == ["cluster-info"]:
        return _cluster_info()

    raise ValueError(
        "Command blocked. Allowed: get pods/nodes/deployments/services/ingress/events, "
        "describe pod <name>, api-resources, version, cluster-info."
    )


# Server-side allowlist: only these workloads' logs may ever be read, always
# in the single fixed namespace this console operates in. No client-supplied
# workload, namespace, or container name is ever trusted.
LOG_WORKLOADS = {
    "migration-app-prod": "deployment",
    "pong-app": "deployment",
    "migration-postgresql": "statefulset",
}


def _workload_pod_selector(name, kind):
    ns = cfg.TARGET_NAMESPACE
    if kind == "deployment":
        obj = _apps.read_namespaced_deployment(name, ns)
    else:
        obj = _apps.read_namespaced_stateful_set(name, ns)
    labels = obj.spec.selector.match_labels or {}
    return ",".join(f"{k}={v}" for k, v in labels.items())


def pod_logs(workload, tail=100):
    if workload not in LOG_WORKLOADS:
        raise ValueError("Unknown or disallowed workload.")
    tail = max(1, min(200, int(tail)))
    ns = cfg.TARGET_NAMESPACE
    try:
        selector = _workload_pod_selector(workload, LOG_WORKLOADS[workload])
        pods = sorted(
            _core.list_namespaced_pod(ns, label_selector=selector).items,
            key=lambda p: p.metadata.name,
        )
    except ApiException as exc:
        raise ValueError(f"Workload {workload} not found ({exc.status})")
    if not pods:
        raise ValueError(f"No Pods found for {workload}.")
    pod_name = pods[0].metadata.name
    try:
        text = _core.read_namespaced_pod_log(
            pod_name, ns, tail_lines=tail, timestamps=False, previous=False
        )
    except ApiException as exc:
        raise ValueError(f"Could not read logs for {pod_name} ({exc.status})")
    return {"workload": workload, "pod": pod_name, "tail": tail, "output": text}


def command_output(command_id):
    commands = {
        "pods": lambda: _pods(False),
        "pods-wide": lambda: _pods(True),
        "nodes": lambda: _nodes(False),
        "nodes-wide": lambda: _nodes(True),
        "deployments": _deployments,
        "services": _services,
        "ingress": _ingress,
        "events": _events,
    }
    if command_id not in commands:
        raise ValueError("Unknown command")
    return commands[command_id]()


def health_summary(db_ok=True):
    nodes = _core.list_node().items
    ready_nodes = sum(1 for n in nodes if any(c.type == "Ready" and c.status == "True" for c in (n.status.conditions or [])))
    st = deployment_state()
    dep_ok = not st.get("error") and st.get("ready") == st.get("desired")
    ing = _net.list_namespaced_ingress(cfg.TARGET_NAMESPACE).items
    all_pods = _core.list_namespaced_pod(cfg.TARGET_NAMESPACE).items
    running = sum(1 for p in all_pods if p.status.phase == "Running")
    return {
        "kubernetes_api": "OK",
        "nodes": f"{ready_nodes}/{len(nodes)} Ready",
        "pods": f"{running}/{len(all_pods)} Running",
        "pong": f"{st.get('ready', 0)}/{st.get('desired', 0)} Ready",
        "rollout": "STABLE" if dep_ok else "CONVERGING",
        "postgresql": "Connected" if db_ok else "Unavailable",
        "ingress": "Ready" if ing else "Missing",
    }


async def watch_pods(queue):
    loop = asyncio.get_running_loop()

    def blocking_watch():
        w = watch.Watch()
        try:
            for ev in w.stream(
                _core.list_namespaced_pod,
                namespace=cfg.TARGET_NAMESPACE,
                label_selector=_selector(),
                timeout_seconds=60,
            ):
                pod = ev["object"]
                phase = "Terminating" if pod.metadata.deletion_timestamp else pod.status.phase
                loop.call_soon_threadsafe(queue.put_nowait, {
                    "kind": "pod", "verb": ev["type"].lower(), "pod": pod.metadata.name, "phase": phase
                })
        finally:
            w.stop()

    while True:
        try:
            await asyncio.to_thread(blocking_watch)
        except Exception as exc:
            await queue.put({"kind": "error", "message": f"Kubernetes watch failed: {exc}"})
            await asyncio.sleep(5)
