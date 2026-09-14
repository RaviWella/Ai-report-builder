node {
    checkout scm

    String targetFile

    if (env.BRANCH_NAME == "main") {
        targetFile = "CICD/Staging/Jenkinsfile"
    } else if (env.BRANCH_NAME == "feat/ai-report-builder") {
        targetFile = "CICD/AIReportBuilder/Jenkinsfile"
    } else {
        error "No Jenkins pipeline is configured for branch '${env.BRANCH_NAME}'. Add a route in the root Jenkinsfile."
    }

    echo "Using pipeline: ${targetFile}"

    def pipelineScript = readFile(targetFile)
    evaluate(pipelineScript)
}
