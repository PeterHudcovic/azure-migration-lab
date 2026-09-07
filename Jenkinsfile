pipeline {
    agent any

    environment {
        ACR_NAME = 'acrmigrationlab'
        ACR_SERVER = 'acrmigrationlab.azurecr.io'
        IMAGE_NAME = 'migration-app'
        RESOURCE_GROUP = 'rg-migration-lab'
        AKS_CLUSTER = 'aks-migration-lab'
        RELEASE_NAME = 'migration-app-prod'
        NAMESPACE = 'prod'
        VALUES_FILE = 'helm/migration-app/values-prod.yaml'

        AZURE_CLIENT_ID = credentials('azure-client-id')
        AZURE_CLIENT_SECRET = credentials('azure-client-secret')
        AZURE_TENANT_ID = credentials('azure-tenant-id')
    }

    stages {
        stage('Build Docker Image') {
            steps {
                sh '''
                    docker build \
                      -t $ACR_SERVER/$IMAGE_NAME:$BUILD_NUMBER \
                      ./app
                '''
            }
        }

        stage('Login to Azure') {
            steps {
                sh '''
                    az login --service-principal \
                      --username "$AZURE_CLIENT_ID" \
                      --password "$AZURE_CLIENT_SECRET" \
                      --tenant "$AZURE_TENANT_ID" \
                      --output none
                '''
            }
        }

        stage('Push Image to ACR') {
            steps {
                sh '''
                    az acr login --name $ACR_NAME
                    docker push $ACR_SERVER/$IMAGE_NAME:$BUILD_NUMBER
                '''
            }
        }

        stage('Deploy to AKS') {
            steps {
                sh '''
                    az aks get-credentials \
                      --resource-group $RESOURCE_GROUP \
                      --name $AKS_CLUSTER \
                      --overwrite-existing

                    helm upgrade --install $RELEASE_NAME ./helm/migration-app \
                      --namespace $NAMESPACE \
                      -f $VALUES_FILE \
                      --set image.repository=$ACR_SERVER/$IMAGE_NAME \
                      --set image.tag=$BUILD_NUMBER
                '''
            }
        }

        stage('Verify Deployment') {
            steps {
                sh '''
                    kubectl get pods -n $NAMESPACE
                    kubectl rollout status deployment/$RELEASE_NAME -n $NAMESPACE
                '''
            }
        }
    }
}