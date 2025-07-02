# Guide d'authentification JWT Cognito pour WebSocket

Ce guide explique comment utiliser le système d'authentification JWT avec Amazon Cognito pour votre API WebSocket.

## Vue d'ensemble

Le système d'authentification utilise :
- **Amazon Cognito User Pool** pour la gestion des utilisateurs
- **JWT (JSON Web Tokens)** pour l'authentification
- **Middleware d'authentification** pour sécuriser les handlers WebSocket
- **DynamoDB** pour le suivi des connexions actives (optionnel)

## Configuration

### 1. Variables d'environnement

Les variables d'environnement suivantes sont requises :

```bash
# Obligatoire
COGNITO_POOL_ID=us-east-1_XXXXXXXXX    # ID du User Pool Cognito
REGION=us-east-1                        # Région AWS
TABLE=your-main-table-name              # Table DynamoDB principale

# Optionnel
COGNITO_CLIENT_ID=your-client-id        # ID du client Cognito (pour validation additionnelle)
CONNECTIONS_TABLE=your-connections-table # Table pour le suivi des connexions
LOG_LEVEL=INFO                          # Niveau de log
```

### 2. Configuration CDK

Pour déployer avec les ressources nécessaires :

```python
# Dans votre stack principal
resources_stack = ResourcesStack(
    app, "ResourcesStack",
    table_name="your-table-name",
    user_pool_id="us-east-1_XXXXXXXXX",
    secret_name="your-secret",
    create_connections_table=True,  # Créer la table de connexions
    # ... autres paramètres
)

lambdas_stack = LambdasStack(
    app, "LambdasStack",
    table_name="your-table-name",
    user_pool_id="us-east-1_XXXXXXXXX",
    api_name="your-api",
    connections_table_name="your-table-name-connections",  # Optionnel
    # ... autres paramètres
)
```

## Utilisation côté client

### 1. Obtenir un token JWT

```python
import boto3

# Authentification avec Cognito
cognito_client = boto3.client('cognito-idp', region_name='us-east-1')

response = cognito_client.initiate_auth(
    ClientId='your-client-id',
    AuthFlow='USER_PASSWORD_AUTH',
    AuthParameters={
        'USERNAME': 'your-username',
        'PASSWORD': 'your-password'
    }
)

access_token = response['AuthenticationResult']['AccessToken']
```

### 2. Connexion WebSocket avec authentification

#### Option A : Token dans les paramètres de requête
```javascript
const ws = new WebSocket('wss://your-api-id.execute-api.region.amazonaws.com/prod?token=' + accessToken);
```

#### Option B : Token dans les headers (si supporté)
```javascript
const ws = new WebSocket('wss://your-api-id.execute-api.region.amazonaws.com/prod', [], {
    headers: {
        'Authorization': 'Bearer ' + accessToken
    }
});
```

### 3. Exemple client Python complet

Voir le fichier `example_websocket_client.py` pour un exemple complet d'utilisation.

## Utilisation côté serveur

### 1. Protection des handlers avec le décorateur

```python
from src.helpers.auth_middleware import authenticate_websocket

@authenticate_websocket()  # Authentification requise
def my_handler(event, context):
    # L'utilisateur est déjà authentifié ici
    # Les informations d'authentification sont disponibles dans event['auth']
    return handle_request(event, context)

@authenticate_websocket(required_groups=['admin', 'moderator'])  # Groupes requis
def admin_handler(event, context):
    # Seuls les utilisateurs des groupes 'admin' ou 'moderator' peuvent accéder
    return handle_admin_request(event, context)
```

### 2. Extraction des informations utilisateur

```python
from src.helpers.auth_middleware import (
    get_authenticated_user, 
    get_user_email, 
    get_user_id, 
    get_username,
    has_group
)

def my_handler(event, context):
    # Obtenir les informations utilisateur
    user_info = get_authenticated_user(event)
    email = get_user_email(event)
    user_id = get_user_id(event)
    username = get_username(event)
    
    # Vérifier l'appartenance à un groupe
    is_admin = has_group(event, 'admin')
    
    # Utiliser ces informations dans votre logique
    validation_schema['datas']['updatedBy'] = email
```

### 3. Authentification manuelle

```python
from src.helpers.auth_middleware import require_authentication

def my_handler(event, context):
    # Vérification manuelle de l'authentification
    auth_result = require_authentication(event)
    
    if not auth_result['success']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': auth_result['error']})
        }
    
    user_info = auth_result['user_info']
    # Continuer avec la logique métier
```

## Gestion des connexions

### 1. Suivi des connexions actives

Le handler `connect` stocke automatiquement les informations de connexion dans DynamoDB :

```python
# Données stockées pour chaque connexion
{
    'connectionId': 'abc123',
    'userId': 'user-uuid',
    'username': 'john.doe',
    'email': 'john@example.com',
    'groups': ['user', 'premium'],
    'connectedAt': 1641000000,
    'ttl': 1641086400  # Expiration automatique après 24h
}
```

### 2. Envoi de messages ciblés

```python
import boto3

def send_message_to_user(user_id: str, message: dict):
    """Envoyer un message à un utilisateur spécifique"""
    dynamodb = boto3.resource('dynamodb')
    connections_table = dynamodb.Table(os.getenv('CONNECTIONS_TABLE'))
    
    # Trouver les connexions de l'utilisateur
    response = connections_table.query(
        IndexName='UserIdIndex',
        KeyConditionExpression='userId = :user_id',
        ExpressionAttributeValues={':user_id': user_id}
    )
    
    # Envoyer le message à toutes les connexions de l'utilisateur
    for connection in response['Items']:
        send_to_client(
            connection['connectionId'], 
            json.dumps(message), 
            websocket_url
        )
```

## Sécurité

### 1. Validation des tokens

- **Signature** : Vérification automatique de la signature JWT
- **Expiration** : Validation de la date d'expiration
- **Issuer** : Vérification de l'émetteur (Cognito)
- **Claims** : Validation des claims personnalisés

### 2. Gestion des erreurs

```python
# Erreurs d'authentification courantes :
# - Token manquant : 401 "Authentication required"
# - Token expiré : 401 "Token has expired"  
# - Signature invalide : 401 "Invalid token signature"
# - Groupes insuffisants : 403 "Insufficient permissions"
```

### 3. Bonnes pratiques

- Utilisez HTTPS/WSS uniquement
- Implémentez une rotation des tokens
- Limitez la durée de vie des tokens
- Surveillez les tentatives d'authentification échouées
- Implémentez un système de rate limiting

## Débogage

### 1. Logs d'authentification

```bash
# Définir le niveau de log pour plus de détails
export LOG_LEVEL=DEBUG
```

### 2. Vérification manuelle des tokens

```python
from src.helpers.cognito_auth import validate_cognito_token

try:
    result = validate_cognito_token(your_token)
    print("Token valide:", result['user_info'])
except Exception as e:
    print("Erreur de validation:", str(e))
```

### 3. Test de connexion

```bash
# Test avec curl (pour REST API, adapter pour WebSocket)
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     https://your-api-id.execute-api.region.amazonaws.com/prod/your-endpoint
```

## Dépendances

Les packages Python suivants sont requis :

```txt
PyJWT[crypto]==2.8.0
requests==2.31.0
cryptography>=41.0.0
boto3
```

## Limitations

- Les tokens JWT ont une durée de vie limitée (configurée dans Cognito)
- Les connexions WebSocket doivent être ré-authentifiées en cas d'expiration du token
- Le cache JWKS a une durée de vie de 1 heure

## Support

Pour des questions ou des problèmes :
1. Vérifiez les logs CloudWatch
2. Validez la configuration Cognito
3. Testez l'authentification avec un client simple
4. Consultez la documentation AWS Cognito
