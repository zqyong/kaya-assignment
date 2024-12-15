# Kaya Challenge
## Prerequisite
1. Python 3.12
2. Docker
3. [uv](https://docs.astral.sh/uv/getting-started/installation/)


## Running locally
1. Create Python virtual environment and install dependencies
```bash
uv python install 3.12
uv sync
```

2. Activate Python virtual environment
```bash
source .venv/bin/activate
```

3.  Launch Docker, uun app and database through Docker
```bash
# make sure Docker is up and running
docker compose up -d
```

4. Run database migration
```bash
# make sure database is up and running via Docker already
alembic upgrade head
```

5. Run data dump
```bash
python utils/dump_csv_data.py
```

Once the app is running, API docs can be locally accessed via [localhost:8000](http://localhost:8000).

## Running tests
```bash
# install app as editable package
uv pip install -e .

# run tests
pytest # runs everything
pytest tests/integration # runs unit/integration tests
pytest tests/api # runs API tests
```

## Cleanup
Stop and remove running containers
```bash
docker compose down --volumes
```

## Solution
I have decided to use FastAPI as the API framework as it is a lightweight and simple framework. The data is modeled via SQLAlchemy ORM and database migrations are handled with Alembic.

The source data was downloaded to [data](/data) as csv files then dumped into PostgreSQL with the [utils/dump_csv_data.py](utils/dump_csv_data.py) script.
Duplicate ad group stats data is aggregated based on date/adgroup ID/device.

Assumptions made:
- The current API does not have authentication implemented.
- The database url is hardcoded. To make this deployable, the url will need to be configurable via a env/config file, code changes are needed.


## Deployment
### Serverless Deployment
The whole FastAPI instance can be packaged (zipped) and deployed as AWS Lambda function. API routing will be handled by API Gateway. A RDS PostgreSQL instance can be created to store data. 

If a custom domain name is required, DNS routing can be configured in Route53 to the API Gateway instance.

For CI/CD, the main pipeline should include the steps as follow:
1. Run linter to check for code quality issues
2. Run unit/integration tests
3. Package and deploy serverless function to AWS
4. Run the API tests (smoke tests) against the updated API instance

Pros:
- Easy to manage
- Cheap at smaller scale
- Scales from zero to the limit of your credit card
- Able to utilize cloud specific IAC tooling (AWS CDK/CloudFormation) for deployments

Cons:
- Vendor lock in to the specific Cloud applications (AWS Lambda/API Gateway)
- May be expensive at scale

### Containerized Deployment
The FastAPI instance is build as a Docker image as a release artifact. The Docker container can then be ran on EC2 instances with Docker installed, or container orchestration platforms like AWS ECS/Kubernetes.

For CI/CD: a typical containerized deployment pipeline looks like this:
1. Run linter to check for code quality issues
2. Run unit/integration tests
3. Build Docker image and publish new version to image repository
4. Push an update to Orchestration platform (eg. ECS/ArgoCD) to use the new image version
5. Orchestration platform handles rolling out and deploying the new image


Pros:
- More fine grained control over application infrastucture
- No vendor lock in
- More compute can be added as required

Cons:
- More management overhead
- Specific tooling expertise needed
- Does not scale to zero
