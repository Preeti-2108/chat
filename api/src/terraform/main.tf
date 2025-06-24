# ######
# ## Variables set in the project level
# ######

variable "APIM_RG" {
  type = string
}

variable "APIM_NAME" {
  type = string
}


variable "AWS_DEFAULT_REGION" {
  type = string
}

variable "AZ_TENANT_ID" {
  type = string
}

variable "AZ_SUB_ID" {
  type = string
}

variable "AZ_CLIENT_ID" {
  type = string
}

variable "AZ_CLIENT_SECRET" {
  type = string
}

# ######
# ## Variables set during the CICD
# ######

variable "APIM_PRODUCT" {
  type = string
}

variable "API_GATEWAY_ENDPOINT" {
  type = string
}

variable "API_SYSTEM_NAME" {
  type = string
}

variable "API_VERSION" {
  type = string
}

variable "ENV" {
  type = string
}

variable "SLS_NAME" {
  type = string
}

# ######
# ## Providers declaration
# ######

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "=5.70.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "=4.12.0"
    }
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
  region     = var.AWS_DEFAULT_REGION
}

terraform {
  backend "s3" {
    bucket = "%bucket%"
    key    = "project/%TF_VAR_APIM_PRODUCT%/%ENV%/ms/%SLS_NAME%.tfstate"
    region = "%AWS_DEFAULT_REGION%"
  }
}

# ######
# ## External data source to extract title from asyncapi.json
# ######

data "external" "asyncapi_title" {
  program = ["sh", "-c", "jq -n --rawfile title ../api/asyncapi.json '{\"title\": ($title | fromjson | .info.title)}'"]
}

# ######
# ## Azure resources
# ######

resource "azurerm_api_management_api" "ics_api" {
  name                = var.SLS_NAME
  resource_group_name = var.APIM_RG
  api_management_name = var.APIM_NAME
  revision            = "1"
  display_name        = "${data.external.asyncapi_title.result.title} - ${var.API_VERSION}"
  path                = "api/${var.API_VERSION}/${var.API_SYSTEM_NAME}"
  protocols           = ["wss"]
  service_url         = var.API_GATEWAY_ENDPOINT
  api_type            = "websocket" # Specify the API type as WebSocket

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

resource "azurerm_storage_account" "ics_products_documentation" {
  name                     = var.APIM_NAME
  resource_group_name      = var.APIM_RG
  location                 = "francecentral"
  account_tier            = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "docs" {
  name                  = var.API_SYSTEM_NAME
  storage_account_name  = azurerm_storage_account.ics_products_documentation.name
  container_access_type = "blob"
}

resource "azurerm_storage_blob" "api_docs" {
  count                 = length(tolist(fileset("output", "*")))
  name                  = basename(tolist(fileset("output", "*"))[count.index])
  storage_account_name  = azurerm_storage_account.ics_products_documentation.name
  storage_container_name = azurerm_storage_container.docs.name
  type                  = "Block"
  source                = "output/${basename(tolist(fileset("output", "*"))[count.index])}"
  content_type          = "text/html"
}

resource "azurerm_storage_blob" "api_docs_css" {
  count                 = length(tolist(fileset("output/css", "*")))
  name                  = "css/${basename(tolist(fileset("output/css", "*"))[count.index])}"
  storage_account_name  = azurerm_storage_account.ics_products_documentation.name
  storage_container_name = azurerm_storage_container.docs.name
  type                  = "Block"
  source                = "output/css/${basename(tolist(fileset("output/css", "*"))[count.index])}"
  content_type          = "text/css"
}

resource "azurerm_storage_blob" "api_docs_js" {
  count                 = length(tolist(fileset("output/js", "*")))
  name                  = "js/${basename(tolist(fileset("output/js", "*"))[count.index])}"
  storage_account_name  = azurerm_storage_account.ics_products_documentation.name
  storage_container_name = azurerm_storage_container.docs.name
  type                  = "Block"
  source                = "output/js/${basename(tolist(fileset("output/js", "*"))[count.index])}"
  content_type          = "application/javascript"
}
