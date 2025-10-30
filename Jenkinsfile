pipeline {
    agent any

    stages {
        stage('Leer entorno desde .env raíz') {
            steps {
                script {
                    def envValue = powershell(
                        script: "(Get-Content .env | Where-Object { \$_ -match '^ENVIRONMENT=' }) -replace '^ENVIRONMENT=', ''",
                        returnStdout: true
                    ).trim()

                    if (!envValue) {
                        error "❌ No se encontró ENVIRONMENT en .env"
                    }

                    env.ENVIRONMENT = envValue
                    env.ENV_DIR = "DevOps/${env.ENVIRONMENT}"
                    env.COMPOSE_FILE = "${env.ENV_DIR}/docker-compose.yml"
                    env.ENV_FILE = "${env.ENV_DIR}/.env"

                    echo "✅ Entorno detectado: ${env.ENVIRONMENT}"
                    echo "📁 Compose: ${env.COMPOSE_FILE}"
                    echo "📄 .env: ${env.ENV_FILE}"
                }
            }
        }

        stage('Construir imagen Docker') {
            steps {
                echo "🐳 Construyendo imagen para ${env.ENVIRONMENT}"
                bat "docker build -t anpr-microservice-${env.ENVIRONMENT}:latest -f Dockerfile ."
            }
        }

        stage('Desplegar microservicio') {
            steps {
                echo "🚀 Desplegando ANPR Microservice (${env.ENVIRONMENT})"
                bat "docker compose -f ${env.COMPOSE_FILE} --env-file ${env.ENV_FILE} up -d --build --remove-orphans"
            }
        }
    }

    post {
        success {
            echo "🎉 Despliegue completado correctamente para ${env.ENVIRONMENT}"
        }
        failure {
            echo "💥 Error durante el despliegue del microservicio (${env.ENVIRONMENT})"
        }
    }
}
