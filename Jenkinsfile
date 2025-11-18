pipeline {
    agent any

    environment {
        DOCKER_CLI_HINTS = "off"
        BASE_IMAGE = "anibal2504/anpr-python-deps:3.12-v0"
    }

    stages {

        stage('Leer entorno desde .env raíz') {
            steps {
                sh '''
                    echo "📂 Leyendo .env raíz..."

                    DEPLOY_ENV=$(grep '^DEPLOY_ENV=' .env | cut -d '=' -f2 | tr -d '\\r\\n')

                    if [ -z "$DEPLOY_ENV" ]; then
                        echo "❌ No se encontró DEPLOY_ENV en .env raíz"
                        exit 1
                    fi

                    echo "🔍 Entorno detectado: $DEPLOY_ENV"

                    echo "DEPLOY_ENV=$DEPLOY_ENV" > env.properties
                    echo "ENV_DIR=DevOps/$DEPLOY_ENV" >> env.properties
                    echo "COMPOSE_FILE=DevOps/$DEPLOY_ENV/docker-compose.yml" >> env.properties
                    echo "ENV_FILE=DevOps/$DEPLOY_ENV/.env" >> env.properties
                '''

                script {
                    def props = readProperties file: 'env.properties'
                    env.DEPLOY_ENV = props['DEPLOY_ENV']
                    env.ENV_DIR = props['ENV_DIR']
                    env.COMPOSE_FILE = props['COMPOSE_FILE']
                    env.ENV_FILE = props['ENV_FILE']

                    echo """
                    🏷 DEPLOY_ENV: ${env.DEPLOY_ENV}
                    📄 Compose:     ${env.COMPOSE_FILE}
                    🌱 Env file:    ${env.ENV_FILE}
                    📁 Dir entorno: ${env.ENV_DIR}
                    """
                }
            }
        }

        stage('Verificar imagen base') {
            steps {
                sh '''
                    echo "🔍 Verificando imagen base $BASE_IMAGE"
                    if ! docker image inspect $BASE_IMAGE > /dev/null 2>&1; then
                        docker pull $BASE_IMAGE
                    else
                        echo "✅ Imagen base ya existe"
                    fi
                '''
            }
        }

        stage('Preparar red') {
            steps {
                sh '''
                    echo "🌐 Creando red anpr-net-${DEPLOY_ENV} si no existe..."
                    docker network create anpr-net-${DEPLOY_ENV} || echo "Ya existe"
                '''
            }
        }

        stage('Construir imagen ANPR Microservice') {
            steps {
                sh '''
                    echo "🐳 Construyendo imagen LOCAL para ${DEPLOY_ENV}..."
                    docker build -t anpr-microservice-${DEPLOY_ENV}:latest -f Dockerfile .
                '''
            }
        }

        stage('Desplegar ANPR Microservice') {
            steps {
                sh '''
                    echo "🚀 Ejecutando docker compose para ${DEPLOY_ENV} (LOCAL, no AWS)..."
                    cd $ENV_DIR
                    docker compose --env-file .env -f docker-compose.yml up -d --build --force-recreate --remove-orphans
                '''
            }
        }
    }

    post {
        success {
            echo "🎉 Despliegue completado para ${env.DEPLOY_ENV}"
        }
        failure {
            echo "💥 Error durante el despliegue (${env.DEPLOY_ENV})"
        }
    }
}
