param(
    [Parameter(Mandatory=$true)][string]$ProjectId,
    [Parameter(Mandatory=$true)][string]$Region,
    [Parameter(Mandatory=$true)][string]$Prefix,
    [Parameter(Mandatory=$true)][string]$CloudSqlTier,
    [Parameter(Mandatory=$true)][string]$GitHubRepository
)

$ErrorActionPreference = "Stop"

$ArtifactRepository = "$Prefix-images"
$SqlInstance = "$Prefix-postgres"
$DatabaseName = "enterprise_ai"
$DatabaseUser = "enterprise_ai"
$BackendSa = "$Prefix-backend"
$McpSa = "$Prefix-mcp"
$MigrationSa = "$Prefix-migrate"
$FrontendSa = "$Prefix-frontend"
$DeploySa = "$Prefix-deploy"
$Pool = "$Prefix-github"
$Provider = "$Prefix-github-repo"

Write-Host "R3 creates billable Google Cloud resources, especially Cloud SQL."
Write-Host "Project=$ProjectId Region=$Region Prefix=$Prefix CloudSqlTier=$CloudSqlTier"
$confirmation = Read-Host "Type CREATE-R3 to continue"
if ($confirmation -ne "CREATE-R3") { throw "Provisioning cancelled." }

gcloud config set project $ProjectId

gcloud services enable `
  run.googleapis.com artifactregistry.googleapis.com sqladmin.googleapis.com `
  secretmanager.googleapis.com iamcredentials.googleapis.com sts.googleapis.com `
  telemetry.googleapis.com cloudtrace.googleapis.com logging.googleapis.com `
  monitoring.googleapis.com serviceusage.googleapis.com

# Artifact Registry.
gcloud artifacts repositories describe $ArtifactRepository --location=$Region 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  gcloud artifacts repositories create $ArtifactRepository --repository-format=docker --location=$Region
}

# Runtime/deployment identities.
foreach ($name in @($BackendSa,$McpSa,$MigrationSa,$DeploySa,$FrontendSa)) {
  gcloud iam service-accounts describe "$name@$ProjectId.iam.gserviceaccount.com" 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) {
    gcloud iam service-accounts create $name --display-name=$name
  }
}

# Cloud SQL. The tier is deliberately supplied by the operator after inspecting
# current regional tiers/pricing rather than hard-coded by the repository.
gcloud sql instances describe $SqlInstance 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  gcloud sql instances create $SqlInstance `
    --database-version=POSTGRES_17 `
    --edition=enterprise `
    --region=$Region `
    --tier=$CloudSqlTier `
    --storage-size=10 `
    --storage-type=SSD

  if ($LASTEXITCODE -ne 0) {
    throw "Failed to create Cloud SQL instance $SqlInstance."
  }
}

gcloud sql databases describe $DatabaseName --instance=$SqlInstance 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  gcloud sql databases create $DatabaseName --instance=$SqlInstance

  if ($LASTEXITCODE -ne 0) {
    throw "Failed to create database $DatabaseName."
  }
}

# Generate an alphanumeric password locally so the SQLAlchemy URL does not need
# special URL escaping. The generated value is written only to Secret Manager.
$alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
$bytes = New-Object byte[] 40
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$dbPassword = -join ($bytes | ForEach-Object { $alphabet[$_ % $alphabet.Length] })

gcloud sql users create $DatabaseUser --instance=$SqlInstance --password=$dbPassword 2>$null
if ($LASTEXITCODE -ne 0) {
  gcloud sql users set-password $DatabaseUser --instance=$SqlInstance --password=$dbPassword

  if ($LASTEXITCODE -ne 0) {
    throw "Failed to create or update database user $DatabaseUser."
  }
}

$ConnectionName = gcloud sql instances describe $SqlInstance --format="value(connectionName)"

if (
  $LASTEXITCODE -ne 0 -or
  [string]::IsNullOrWhiteSpace($ConnectionName)
) {
  throw "Failed to resolve Cloud SQL connection name for $SqlInstance."
}

$DatabaseUrl = "postgresql+psycopg://$DatabaseUser`:$dbPassword@/$DatabaseName`?host=/cloudsql/$ConnectionName"

function Ensure-Secret([string]$Name) {
  gcloud secrets describe $Name 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) { gcloud secrets create $Name --replication-policy=automatic }
}
function Add-SecretValue([string]$Name,[string]$Value) {
  $tempPath = Join-Path ([System.IO.Path]::GetTempPath()) ("enterprise-ai-secret-" + [guid]::NewGuid().ToString("N") + ".txt")

  try {
    [System.IO.File]::WriteAllText($tempPath,$Value,[System.Text.UTF8Encoding]::new($false))

    gcloud secrets versions add $Name --data-file=$tempPath | Out-Null

    if ($LASTEXITCODE -ne 0) {
      throw "Failed to add a secret version for $Name."
    }
  }
  finally {
    Remove-Item $tempPath -Force -ErrorAction SilentlyContinue
  }
}

$DbSecret = "$Prefix-database-url"
$JwtSecret = "$Prefix-jwt-secret"
$OpenAiSecret = "$Prefix-openai-api-key"
$GeminiSecret = "$Prefix-gemini-api-key"
foreach ($secret in @($DbSecret,$JwtSecret,$OpenAiSecret,$GeminiSecret)) { Ensure-Secret $secret }
Add-SecretValue $DbSecret $DatabaseUrl

# JWT is generated; provider keys are intentionally added later by the operator.
$jwtBytes = New-Object byte[] 48
[System.Security.Cryptography.RandomNumberGenerator]::Fill($jwtBytes)
$jwtSecretValue = [Convert]::ToBase64String($jwtBytes)
Add-SecretValue $JwtSecret $jwtSecretValue

$BackendEmail="$BackendSa@$ProjectId.iam.gserviceaccount.com"
$McpEmail="$McpSa@$ProjectId.iam.gserviceaccount.com"
$MigrationEmail="$MigrationSa@$ProjectId.iam.gserviceaccount.com"
$FrontendEmail="$FrontendSa@$ProjectId.iam.gserviceaccount.com"
$DeployEmail="$DeploySa@$ProjectId.iam.gserviceaccount.com"

foreach ($email in @($BackendEmail,$McpEmail,$MigrationEmail)) {
  gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$email" --role="roles/cloudsql.client" | Out-Null
}
foreach ($email in @($BackendEmail,$McpEmail)) {
  gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$email" --role="roles/telemetry.tracesWriter" | Out-Null
  gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$email" --role="roles/serviceusage.serviceUsageConsumer" | Out-Null
}

# Secret access is intentionally per secret/service identity.
foreach ($email in @($BackendEmail,$McpEmail,$MigrationEmail)) {
  gcloud secrets add-iam-policy-binding $DbSecret --member="serviceAccount:$email" --role="roles/secretmanager.secretAccessor" | Out-Null
}
gcloud secrets add-iam-policy-binding $JwtSecret --member="serviceAccount:$BackendEmail" --role="roles/secretmanager.secretAccessor" | Out-Null
gcloud secrets add-iam-policy-binding $OpenAiSecret --member="serviceAccount:$BackendEmail" --role="roles/secretmanager.secretAccessor" | Out-Null
gcloud secrets add-iam-policy-binding $GeminiSecret --member="serviceAccount:$BackendEmail" --role="roles/secretmanager.secretAccessor" | Out-Null

# Deployment identity: bounded deployment permissions, not Owner/Editor.
foreach ($role in @("roles/run.admin","roles/artifactregistry.writer")) {
  gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$DeployEmail" --role=$role | Out-Null
}
foreach ($email in @($BackendEmail,$McpEmail,$MigrationEmail,$FrontendEmail)) {
  gcloud iam service-accounts add-iam-policy-binding $email --member="serviceAccount:$DeployEmail" --role="roles/iam.serviceAccountUser" | Out-Null
}

# GitHub OIDC/WIF through the bounded deployment service account.
gcloud iam workload-identity-pools describe $Pool --location=global 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  gcloud iam workload-identity-pools create $Pool --location=global --display-name="$Prefix GitHub"
}
$PoolName = gcloud iam workload-identity-pools describe $Pool --location=global --format="value(name)"

gcloud iam workload-identity-pools providers describe $Provider --location=global --workload-identity-pool=$Pool 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  gcloud iam workload-identity-pools providers create-oidc $Provider `
    --location=global `
    --workload-identity-pool=$Pool `
    --issuer-uri="https://token.actions.githubusercontent.com" `
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" `
    --attribute-condition="assertion.repository == '$GitHubRepository' && assertion.ref == 'refs/heads/main'"
}
$ProviderName = gcloud iam workload-identity-pools providers describe $Provider --location=global --workload-identity-pool=$Pool --format="value(name)"
gcloud iam service-accounts add-iam-policy-binding $DeployEmail `
  --role="roles/iam.workloadIdentityUser" `
  --member="principalSet://iam.googleapis.com/$PoolName/attribute.repository/$GitHubRepository" | Out-Null

Write-Host "Provisioning complete. Add provider secret versions before deployment:"
Write-Host "  OpenAI:  $OpenAiSecret"
Write-Host "  Gemini:  $GeminiSecret"
Write-Host "Repository variables for deploy-gcp.yml:"
Write-Host "  GCP_PROJECT_ID=$ProjectId"
Write-Host "  GCP_REGION=$Region"
Write-Host "  GCP_ENV_PREFIX=$Prefix"
Write-Host "  GCP_ARTIFACT_REPOSITORY=$ArtifactRepository"
Write-Host "  GCP_WIF_PROVIDER=$ProviderName"
Write-Host "  GCP_DEPLOY_SERVICE_ACCOUNT=$DeployEmail"
Write-Host "  CLOUD_SQL_CONNECTION_NAME=$ConnectionName"
Write-Host "  FRONTEND_SERVICE_ACCOUNT=$FrontendEmail"
Write-Host "  BACKEND_SERVICE_ACCOUNT=$BackendEmail"
Write-Host "  MCP_SERVICE_ACCOUNT=$McpEmail"
Write-Host "  MIGRATION_SERVICE_ACCOUNT=$MigrationEmail"
Write-Host "  DATABASE_URL_SECRET=$DbSecret"
Write-Host "  JWT_SECRET=$JwtSecret"
Write-Host "  OPENAI_API_KEY_SECRET=$OpenAiSecret"
Write-Host "  GEMINI_API_KEY_SECRET=$GeminiSecret"
