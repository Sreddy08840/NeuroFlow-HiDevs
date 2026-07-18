.PHONY: security-scan
security-scan:
	docker compose -f infra/docker-compose.prod.yml build api
	trivy image --severity CRITICAL --exit-code 1 neuroflow-api:latest
