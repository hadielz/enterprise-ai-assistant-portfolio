$ErrorActionPreference = "Stop"

Write-Host "Starting PostgreSQL test database..."
docker compose up -d postgres-test

Write-Host "Waiting for PostgreSQL test database..."
$maxAttempts = 30

for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    docker compose exec -T postgres-test `
        pg_isready `
        -U enterprise_ai_test `
        -d enterprise_ai_test *> $null

    if ($LASTEXITCODE -eq 0) {
        break
    }

    if ($attempt -eq $maxAttempts) {
        throw "PostgreSQL test database did not become ready."
    }

    Start-Sleep -Seconds 1
}

Write-Host "Running isolated test suite..."
docker compose run --rm --no-deps `
    --volume "${PWD}:/app" `
    --workdir /app `
    backend `
    pytest -v

if ($LASTEXITCODE -ne 0) {
    throw "Tests failed."
}

Write-Host "All tests passed."