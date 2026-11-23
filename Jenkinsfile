
pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        timeout(time: 20, unit: 'MINUTES')
    }

    environment {
        COMPOSE_PROJECT_NAME = "activolab-ci-${BUILD_NUMBER}"
        HTTP_PORT = '18080'
        APP_IMAGE = "activolab-ci:${BUILD_NUMBER}"
    }

    stages {

        stage('Preparar entorno') {
            steps {
                sh '''
                    cat > .env <<EOF
COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME
HTTP_PORT=18080
APP_IMAGE=$APP_IMAGE
APP_NAME=ActivoLab CI
ORG_NAME=Laboratorio
MYSQL_ROOT_PASSWORD=RootPruebas2026
MYSQL_DATABASE=inventario_ci
MYSQL_USER=inventario
MYSQL_PASSWORD=MySQLPruebas2026
APP_USERNAME=admin
APP_PASSWORD=AdminPruebas2026
FLASK_SECRET_KEY=clave-exclusiva-laboratorio-ci
EOF
                    chmod 600 .env
                    docker version
                    docker compose version
                '''
            }
        }

        stage('Validar configuracion') {
            steps {
                sh 'docker compose config -q'
                sh 'python3 -m compileall -q app'
                sh 'find scripts -name "*.sh" -exec bash -n {} +'
            }
        }

        stage('Construir imagen') {
            steps {
                sh 'docker compose build app'
            }
        }

        stage('Desplegar contenedores') {
            steps {
                sh '''
                    docker compose up -d --no-build --wait --wait-timeout 240
                    docker compose ps
                '''
            }
        }

        stage('Validar aplicacion web') {
            steps {
                sh '''
                    curl -fsS --retry 10 --retry-connrefused \
                    http://127.0.0.1:18080/health
                '''
            }
        }

        stage('Validar base de datos') {
            steps {
                sh '''
                    docker compose exec -T db sh -ec '
                        MYSQL_PWD="$MYSQL_PASSWORD" mysql \
                        -u "$MYSQL_USER" "$MYSQL_DATABASE" \
                        -e "SELECT 1;"
                    '
                '''
            }
        }

        stage('Comprobar persistencia') {
            steps {
                sh '''
                    docker compose exec -T db sh -ec '
                        MYSQL_PWD="$MYSQL_PASSWORD" mysql \
                        -u "$MYSQL_USER" "$MYSQL_DATABASE" \
                        -e "CREATE TABLE IF NOT EXISTS ci_check (id INT PRIMARY KEY); REPLACE INTO ci_check VALUES (1);"
                    '

                    docker compose up -d --no-build --force-recreate \
                    --wait --wait-timeout 240

                    docker compose exec -T db sh -ec '
                        MYSQL_PWD="$MYSQL_PASSWORD" mysql \
                        -N -B -u "$MYSQL_USER" "$MYSQL_DATABASE" \
                        -e "SELECT COUNT(*) FROM ci_check WHERE id=1;"
                    ' | grep -qx 1

                    curl -fsS http://127.0.0.1:18080/health
                '''
            }
        }
    }

    post {
        success {
            echo 'Validacion de ActivoLab exitosa'
        }

        failure {
            echo 'Se encontraron errores durante la validacion'
        }

        always {
            sh '''
                if [ -f .env ]; then
                    docker compose logs --tail=50 || true
                    docker compose down -v --remove-orphans
                    rm -f .env
                fi
            '''
        }
    }
}

