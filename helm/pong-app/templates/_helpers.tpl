{{- define "pong-app.name" -}}
pong-app
{{- end }}

{{- define "pong-app.fullname" -}}
{{- if .Release.Name }}
{{ .Release.Name }}
{{- else }}
pong-app
{{- end }}
{{- end }}
