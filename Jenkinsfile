pipeline {
    agent any

    environment {
        DOCKER_CLI_HINTS = "off" // evita warnings molestos
        BASE_IMAGE = "anibal2504/anpr-python-deps:3.12-v0" // imagen base precompilada
    }

    stages {

        // =====================================================
        // 1️⃣ Leer entorno desde .env raíz
        // =====================================================
        stage('Leer entorno desde .env raíz') {
            steps {
                sh '''
                    echo "📂 Leyendo entorno desde .env"

                    # Extraer la variable DEPLOY_ENV del archivo .env raíz
                    DEPLOY_ENV=$(grep '^DEPLOY_ENV=' .env | cut -d '=' -f2 | tr -d '\\r\\n')

                    if [ -z "$DEPLOY_ENV" ]; then
                        echo "❌ No se encontró DEPLOY_ENV en .env"
                        exit 1
                    fi

                    echo "✅ Entorno detectado: $DEPLOY_ENV"
                    echo "DEPLOY_ENV=$DEPLOY_ENV" >> env.properties
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
                }
            }
        }

        // =====================================================
        // 2️⃣ Verificar imagen base
        // =====================================================
        stage('Verificar imagen base') {
            steps {
                sh '''
                    echo "🔍 Verificando si existe imagen base $BASE_IMAGE"
                    if ! docker image inspect $BASE_IMAGE > /dev/null 2>&1; then
                        echo "⬇️ Descargando imagen base..."
                        docker pull $BASE_IMAGE
                    else
                        echo "✅ Imagen base ya disponible localmente"
                    fi
                '''
            }
        }

        // =====================================================
        // 3️⃣ Construir imagen del microservicio
        // =====================================================
        stage('Construir imagen Docker') {
            steps {
                sh '''
                    echo "🐳 Construyendo imagen del microservicio para $DEPLOY_ENV"
                    docker build -t anpr-microservice-$DEPLOY_ENV:latest -f Dockerfile .
                '''
            }
        }

        // =====================================================
        // 4️⃣ Desplegar microservicio (Docker Compose)
        // =====================================================
        stage('Desplegar microservicio') {
            steps {
                sh '''
                    echo "🚀 Desplegando ANPR Microservice ($DEPLOY_ENV)"
                    docker compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d --build --remove-orphans
                '''
            }
        }
    }

    // =========================================================
    //  Post actions (notificaciones de éxito o error)
    // =========================================================
    post {
        success {
            echo "🎉 Despliegue completado correctamente para ${env.DEPLOY_ENV}"
        }
        failure {
            echo "💥 Error durante el despliegue del microservicio (${env.DEPLOY_ENV})"
        }
    }
}

