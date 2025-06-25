const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

const asyncapiDefinition = {
    "asyncapi": "2.6.0",
    "id": "urn:templatepython:api",
    "defaultContentType": "application/json",
    "info": {
      "title": "Python Template CDK Websocket",
      "version": "1.0.0",
      "description": "API for Template",
      "contact": {
        "name": "API Support",
        "email": "support.dps.fr.api.contact@soprasteria.com",
        "url": "https://example.com/support"
      }
    },
    "tags": [
      {
        "name": "Template",
        "description": "Operations related to template"
      }
    ],
    "servers": {
      "production": {
        "url": "%BASE_URL%%TF_VAR_API_VERSION%/%TF_VAR_API_SYSTEM_NAME%",
        "protocol": "wss"
      }
    }
};
 
// Fonction pour lire les fichiers et générer la documentation AsyncAPI
async function generateAsyncAPIDocument(baseDir = './src') {
    let channels = {}; // Initialiser channels en dehors de l'objet asyncAPIDocument
    let components = {}; // Initialiser components en dehors de l'objet asyncAPIDocument

    async function readFilesRecursively(dir) {
        const entries = await fs.promises.readdir(dir, { withFileTypes: true });
        for (const entry of entries) {
            const fullPath = path.join(dir, entry.name);
            if (entry.isDirectory()) {
                await readFilesRecursively(fullPath);
            } else if (entry.isFile() && entry.name.endsWith('.py')) {
                try {
                    const content = await fs.promises.readFile(fullPath, 'utf-8');
                    const asyncapiAnnotation = extractAsyncAPIAnnotation(content);
                    if (asyncapiAnnotation) {
                        const fileChannels = asyncapiAnnotation.channels;
                        if (fileChannels && Object.keys(fileChannels).length > 0) {
                            for (const channel of Object.keys(fileChannels)) {
                                // Assurez-vous que vous fusionnez correctement les canaux
                                channels[channel] = {
                                    ...channels[channel],
                                    ...fileChannels[channel],
                                };
                            }
                        }
                        const fileComponents = asyncapiAnnotation.components;
                        if (fileComponents) {
                            components = {
                                ...components,
                                ...fileComponents,
                            };
                        }
                    }
                } catch (err) {
                    console.error(`Error reading file ${fullPath}:`, err);
                }
            }
        }
    }    

    function extractAsyncAPIAnnotation(content) {
        const asyncapiRegex = /\/\*\*[\s\S]*?\*\//g;
        const match = content.match(asyncapiRegex);
        if (match) {
            const annotation = match[0]
                .replace(/\/\*\*|\*\//g, '')
                .replace(/\*/g, '')
                .replace('@asyncapi', '')
                .trim();
            try {
                return yaml.load(annotation);
            } catch (error) {
                console.error(`Error parsing AsyncAPI annotation:`, error);
            }
        }
    }

    await readFilesRecursively(baseDir);

    let asyncAPIDocument = {
        ...asyncapiDefinition,
        channels: channels, // Ajouter channels à l'objet asyncAPIDocument
        components: components, // Ajouter components à l'objet asyncAPIDocument
    };

    // Écrire la documentation dans asyncapi.json
    const outputPath = path.join(__dirname, '../api/asyncapi.json');
    try {
        await fs.promises.writeFile(outputPath, JSON.stringify(asyncAPIDocument, null, 2), 'utf-8');
        console.log('Created asyncapi.json file successfully.');
    } catch (error) {
        console.error('Error writing asyncapi.json file:', error);
    }
}

// Exécuter la génération
generateAsyncAPIDocument().catch((error) => {
    console.error('Error generating AsyncAPI document:', error);
});