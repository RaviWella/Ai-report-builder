node {
    checkout scm

    String targetFile

    if (env.BRANCH_NAME == "main") {
        targetFile = "CICD/Prod/Jenkinsfile"

    }else if (env.BRANCH_NAME == "main_dev") {
        targetFile = "CICD/Staging/Jenkinsfile"

    }

    echo "Using pipeline: ${targetFile}"

    def pipelineScript = readFile(targetFile)
    evaluate(pipelineScript)
}
