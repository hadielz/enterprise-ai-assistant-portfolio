param(
    [Parameter(Mandatory=$true)][string]$ProjectId,
    [Parameter(Mandatory=$true)][string]$Region,
    [Parameter(Mandatory=$true)][string]$Prefix
)
$ErrorActionPreference = "Stop"
Write-Host "This deletes the R3 Cloud Run services/job, Cloud SQL instance, and Artifact Registry repository."
$confirmation = Read-Host "Type DELETE-R3 to continue"
if ($confirmation -ne "DELETE-R3") { throw "Teardown cancelled." }

gcloud config set project $ProjectId
foreach ($service in @("$Prefix-frontend","$Prefix-backend","$Prefix-mcp")) {
  gcloud run services delete $service --region=$Region --quiet 2>$null
}
gcloud run jobs delete "$Prefix-migrate" --region=$Region --quiet 2>$null
gcloud sql instances delete "$Prefix-postgres" --quiet 2>$null
gcloud artifacts repositories delete "$Prefix-images" --location=$Region --quiet 2>$null
Write-Host "Secrets, service accounts, and WIF resources were intentionally left for explicit review/removal."
