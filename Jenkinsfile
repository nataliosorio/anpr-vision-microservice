pipeline {
    agent any

    environment {
        DOCKER_CLI_HINTS = "off" // evita warnings en algunos entornos
    }

    stages {
        stage('Leer entorno desde .env raíz') {
            steps {
                sh '''
                    echo "📂 Leyendo entorno desde .env"

                    # Extraer la variable ENVIRONMENT del archivo .env
                    ENVIRONMENT=$(grep '^ENVIRONMENT=' .env | cut -d '=' -f2 | tr -d '\\r\\n')

                    if [ -z "$ENVIRONMENT" ]; then
                        echo "❌ No se encontró ENVIRONMENT en .env"
                        exit 1
                    fi

                    echo "✅ Entorno detectado: $ENVIRONMENT"
                    echo "ENVIRONMENT=$ENVIRONMENT" >> env.properties
                    echo "ENV_DIR=DevOps/$ENVIRONMENT" >> env.properties
                    echo "COMPOSE_FILE=DevOps/$ENVIRONMENT/docker-compose.yml" >> env.properties
                    echo "ENV_FILE=DevOps/$ENVIRONMENT/.env" >> env.properties
                '''
                script {
                    def props = readProperties file: 'env.properties'
                    env.ENVIRONMENT = props['ENVIRONMENT']
                    env.ENV_DIR = props['ENV_DIR']
                    env.COMPOSE_FILE = props['COMPOSE_FILE']
                    env.ENV_FILE = props['ENV_FILE']
                }
            }
        }

        stage('Construir imagen Docker') {
            steps {
                sh '''
                    echo "🐳 Construyendo imagen para $ENVIRONMENT"
                    docker build -t anpr-microservice-$ENVIRONMENT:latest -f Dockerfile .
                '''
            }
        }

        stage('Desplegar microservicio') {
            steps {
                sh '''
                    echo "🚀 Desplegando ANPR Microservice ($ENVIRONMENT)"
                    docker compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d --build --remove-orphans
                '''
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

