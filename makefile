# Ruff を動作させる
.PHONY: lint format all

lint:
	poetry run ruff check

fmt:
	poetry run ruff check --fix

all: fmt lint

# Terraform をルートディレクトリから動作させる
TF_DIR=terraform

init:
	terraform -chdir=$(TF_DIR) init

plan:
	terraform -chdir=$(TF_DIR) plan

apply:
	terraform -chdir=$(TF_DIR) apply
# brew install graphviz でインストールが必要(macOS)
graph:
	terraform -chdir=$(TF_DIR) graph | dot -Tpng > terraform_graph.png