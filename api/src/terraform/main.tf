# -----------------------------------------------------
# Variables - Projet
# -----------------------------------------------------

variable "APIM_RG"                { type = string }
variable "APIM_NAME"              { type = string }
variable "AWS_DEFAULT_REGION"     { type = string }
variable "AZ_TENANT_ID"           { type = string }
variable "AZ_SUB_ID"              { type = string }
variable "AZ_CLIENT_ID"           { type = string }
variable "AZ_CLIENT_SECRET"       { type = string }

# -----------------------------------------------------
# Variables - CICD
# -----------------------------------------------------

variable "APIM_PRODUCT"           { type = string }
variable "API_GATEWAY_ENDPOINT"   { type = string }
variable "API_SYSTEM_NAME"        { type = string }
variable "API_VERSION"            { type = string }
variable "ENV"                    { type = string }
variable "SLS_NAME"               { type = string }

# -----------------------------------------------------
# Terraform Providers et Backend
# -----------------------------------------------------

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.80.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0.0"
    }
  }

  backend "s3" {
    bucket = "nom-de-ton-bucket"
    key    = "project/${var.APIM_PRODUCT}/${var.ENV}/ms/${var.SLS_NAME}.tfstate"
    region = "eu-west-3"
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.AZ_SUB_ID
  client_id       = var.AZ_CLIENT_ID
  client_secret   = var.AZ_CLIENT_SECRET
  tenant_id       = var.AZ_TENANT_ID
}

provider "aws" {
  region = var.AWS_DEFAULT_REGION
}

# -----------------------------------------------------
# External - Récupération du titre depuis asyncapi.json
# -----------------------------------------------------

data "external" "asyncapi_title" {
  program = [
    "sh", "-c",
    "jq -n --rawfile title ../api/asyncapi.json '{\"title\": ( ($title | fromjson).info.title )}'"
  ]
}

# -----------------------------------------------------
# Azure API Management API
# -----------------------------------------------------

resource "azurerm_api_management_api" "ics_api" {
  name                = var.SLS_NAME
  resource_group_name = var.APIM_RG
  api_management_name = var.APIM_NAME
  revision            = "1"

  display_name = "${data.external.asyncapi_title.result.title} - ${var.API_VERSION}"
  path         = "api/${var.API_VERSION}/${var.API_SYSTEM_NAME}"
  protocols    = ["wss"]
  api_type     = "websocket"
  service_url  = var.API_GATEWAY_ENDPOINT

  subscription_key_parameter_names {
    header = "api-key"
    query  = "api-key"
  }

  description = "Documentation : https://${var.APIM_NAME}.blob.core.windows.net/${var.API_SYSTEM_NAME}/index.html"
}

resource "azurerm_api_management_product_api" "ics_product_api" {
  api_name            = azurerm_api_management_api.ics_api.name
  product_id          = var.APIM_PRODUCT
  api_management_name = var.APIM_NAME
  resource_group_name = var.APIM_RG
}

# -----------------------------------------------------
# Azure Storage pour documentation API
# -----------------------------------------------------

resource "azurerm_storage_account" "ics_products_documentation" {
  name                     = lower(replace(var.APIM_NAME, "-", ""))
  resource_group_name      = var.APIM_RG
  location                 = "francecentral"
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "docs" {
  name                  = var.API_SYSTEM_NAME
  storage_account_id    = azurerm_storage_account.ics_products_documentation.id
  container_access_type = "blob"
}

# Upload des fichiers HTML
resource "azurerm_storage_blob" "api_docs" {
  for_each = { for file in fileset("output", "*") : file => file }

  name                   = each.key
  storage_account_name   = azurerm_storage_account.ics_products_documentation.name
  storage_container_name = azurerm_storage_container.docs.name
  type                   = "Block"
  source                 = "output/${each.key}"
  content_type           = "text/html"
}

# Upload des fichiers CSS
resource "azurerm_storage_blob" "api_docs_css" {
  for_each = { for file in fileset("output/css", "*") : file => file }

  name                   = "css/${each.key}"
  storage_account_name   = azurerm_storage_account.ics_products_documentation.name
  storage_container_name = azurerm_storage_container.docs.name
  type                   = "Block"
  source                 = "output/css/${each.key}"
  content_type           = "text/css"
}

# Upload des fichiers JS
resource "azurerm_storage_blob" "api_docs_js" {
  for_each = { for file in fileset("output/js", "*") : file => file }

  name                   = "js/${each.key}"
  storage_account_name   = azurerm_storage_account.ics_products_documentation.name
  storage_container_name = azurerm_storage_container.docs.name
  type                   = "Block"
  source                 = "output/js/${each.key}"
  content_type           = "application/javascript"
}
