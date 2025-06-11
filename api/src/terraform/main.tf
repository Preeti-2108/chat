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
# ## External data source to extract title from swagger.json
# ######

data "external" "swagger_title" {
  program = ["sh", "-c", "jq -n --rawfile title ../api/swagger.json '{\"title\": ($title | fromjson | .info.title)}'"]
}

# ######
# ## Azure resources
# ######

resource "azurerm_api_management_api" "ics_api" {
  name                = var.SLS_NAME
  resource_group_name = var.APIM_RG
  api_management_name = var.APIM_NAME
  revision            = "1"
  display_name        = "${data.external.swagger_title.result.title} - ${var.API_VERSION}"
  path                = "api/${var.API_VERSION}/${var.API_SYSTEM_NAME}"
  protocols           = ["https"]
  service_url         = var.API_GATEWAY_ENDPOINT
  subscription_key_parameter_names {
    header = "api-key"
    query  = "api-key"
  }
}

resource "azurerm_api_management_api_policy" "ics_policy" {
  api_name            = azurerm_api_management_api.ics_api.name
  api_management_name = var.APIM_NAME
  resource_group_name = var.APIM_RG

  xml_content = file("../api/policies.xml")
}

resource "azurerm_api_management_product_api" "ics_product_api" {
  api_name            = azurerm_api_management_api.ics_api.name
  product_id          = var.APIM_PRODUCT
  api_management_name = var.APIM_NAME
  resource_group_name = var.APIM_RG
}
