// Example Jenkinsfile for running Coroner gate in CI.
// Not executed by this repository's CI.

pipeline {
    agent any
    
    stages {
        stage('Build') {
            steps {
                sh 'docker build --platform linux/amd64 -t coroner:ci .'
            }
        }
        
        stage('Gate') {
            steps {
                script {
                    sh '''
                        docker run --init --platform linux/amd64 \
                            --name coroner-gate-${BUILD_NUMBER} \
                            -e CORONER_BASE_DIR=/tmp/coroner-runs \
                            coroner:ci \
                            python3 -m coroner gate --junit /tmp/gate.xml
                    '''
                }
            }
        }
    }
    
    post {
        always {
            sh '''
                docker cp coroner-gate-${BUILD_NUMBER}:/tmp/gate.xml ./gate.xml || true
                docker rm -f coroner-gate-${BUILD_NUMBER} || true
            '''
            junit 'gate.xml'
        }
    }
}
