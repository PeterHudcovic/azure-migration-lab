pipeline {
    agent any

    environment {
        ACR_NAME       = 'acrmigrationlab'
        ACR_SERVER     = 'acrmigrationlab.azurecr.io'
        IMAGE_NAME     = 'migration-app'
        RESOURCE_GROUP = 'rg-migration-lab'
        AKS_CLUSTER    = 'aks-migration-lab'

        AZURE_CLIENT_ID     = credentials('azure-client-id')
        AZURE_CLIENT_SECRET = credentials('azure-client-secret')
        AZURE_TENANT_ID     = credentials('azure-tenant-id')
        POSTGRES_PASSWORD   = credentials('postgres-password')
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
                      --tenant "$AZURE_TENANT_ID"
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

                    helm upgrade --install migration-app ./helm/migration-app \
                      --set image.repository=$ACR_SERVER/$IMAGE_NAME \
                      --set image.tag=$BUILD_NUMBER \
                      --set-string postgresql.password="$POSTGRES_PASSWORD"
                '''
            }
        }

        stage('Verify Deployment') {
            steps {
                sh '''
                    kubectl get pods
                    kubectl rollout status deployment/migration-app
                '''
            }
        }
    }
}