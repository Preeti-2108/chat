# Guide de Configuration des Variables d'Environnement

## 📋 Variables d'environnement pour WebSocket Auth

### 🔧 Variables à configurer manuellement

Ces variables doivent être définies **avant** le déploiement :

| Variable | Description | Exemple | Requis |
|----------|-------------|---------|---------|
| `TABLE` | Nom de la table DynamoDB pour les connexions | `websocket-connections` | ✅ Oui |
| `COGNITO_POOL_ID` | ID du User Pool Cognito | `us-east-1_abcdef123` | ✅ Oui |
| `REGION` | Région AWS | `us-east-1` | ✅ Oui |
| `LOG_LEVEL` | Niveau de logging | `INFO` ou `DEBUG` | ❌ Non |

### 🚀 Variables générées automatiquement

Ces variables sont créées **pendant** le déploiement par votre infrastructure :

| Variable | Description | Générée par | Quand |
|----------|-------------|-------------|--------|
| `WEBSOCKET_ENDPOINT_URL` | URL de l'API Gateway WebSocket | CDK/CloudFormation | Lors du déploiement |

## 🏗️ Configuration selon l'environnement

### Développement local
```bash
# Définir les variables requises
export TABLE=websocket-connections-dev
export COGNITO_POOL_ID=us-east-1_abc123
export REGION=us-east-1
export LOG_LEVEL=DEBUG

# WEBSOCKET_ENDPOINT_URL n'est pas nécessaire pour les tests unitaires
```

### Déploiement avec CDK
```typescript
// Dans votre stack CDK
const websocketApi = new ApiGatewayV2.WebSocketApi(this, 'WebSocketApi', {
  // configuration...
});

// La variable WEBSOCKET_ENDPOINT_URL sera automatiquement définie
const websocketUrl = websocketApi.apiEndpoint;

// Ajout aux variables d'environnement des Lambda functions
const lambdaFunction = new Function(this, 'MyFunction', {
  environment: {
    TABLE: table.tableName,
    COGNITO_POOL_ID: userPool.userPoolId,
    REGION: this.region,
    WEBSOCKET_ENDPOINT_URL: websocketUrl  // ← Générée automatiquement
  }
});
```

### Déploiement avec CloudFormation
```yaml
# Dans votre template CloudFormation
Resources:
  WebSocketApi:
    Type: AWS::ApiGatewayV2::Api
    Properties:
      ProtocolType: WEBSOCKET
  
  LambdaFunction:
    Type: AWS::Lambda::Function
    Properties:
      Environment:
        Variables:
          TABLE: !Ref ConnectionsTable
          COGNITO_POOL_ID: !Ref UserPool
          REGION: !Ref AWS::Region
          WEBSOCKET_ENDPOINT_URL: !Sub 'https://${WebSocketApi}.execute-api.${AWS::Region}.amazonaws.com/${Stage}'
```

## ✅ Vérification de la configuration

### Script de vérification
```bash
# Exécuter le script de vérification
python check_websocket_auth.py
```

### Statuts possibles
- ✅ **Toutes les variables définies** : Prêt pour la production
- ✅ **Variables requises présentes** : Prêt pour le déploiement (WEBSOCKET_ENDPOINT_URL sera générée)
- ❌ **Variables manquantes** : Configuration incomplète

## 🔄 Workflow de déploiement

1. **Avant le déploiement** :
   ```bash
   # Configurer les variables requises
   export TABLE=my-websocket-table
   export COGNITO_POOL_ID=us-east-1_abc123
   export REGION=us-east-1
   ```

2. **Pendant le déploiement** :
   - CDK/CloudFormation crée l'API Gateway WebSocket
   - `WEBSOCKET_ENDPOINT_URL` est automatiquement générée
   - Toutes les Lambda functions reçoivent les variables d'environnement

3. **Après le déploiement** :
   ```bash
   # Vérifier que tout fonctionne
   python check_websocket_auth.py
   ```

## 🐛 Dépannage

### Erreur : "WEBSOCKET_ENDPOINT_URL not set"
- **En développement** : Normal, cette variable n'est pas nécessaire pour les tests
- **En production** : Vérifier que le déploiement s'est bien déroulé

### Erreur : "TABLE not set"
- Définir la variable avant le déploiement
- Vérifier que la table DynamoDB existe

### Erreur : "COGNITO_POOL_ID not set"
- S'assurer que le User Pool Cognito est créé
- Récupérer l'ID depuis la console AWS ou le script de déploiement
