// Import the 'fs' module for file system operations
const fs = require('fs');
// Import the 'path' module for handling and transforming file paths
const path = require('path');
// Import the 'js-yaml' module to parse YAML content
const yaml = require('js-yaml');

// Define the base AsyncAPI document structure
const asyncapiDefinition = {
    "asyncapi": "2.6.0", // Specify the AsyncAPI version
    "id": "urn:templatepython:api", // Unique identifier for the API
    "defaultContentType": "application/json", // Default content type for messages
    "info": {
      "title": "Python Template CDK Websocket", // Title of the API
      "version": "1.0.1", // Version of the API
      "description": "API for Template", // Brief description of the API
      "contact": {
        "name": "API Support", // Contact name for API support
        "email": "support.dps.fr.api.contact@soprasteria.com", // Contact email for API support
        "url": "https://example.com/support" // URL for support
      },
      "license": {
        "name": "MIT", // License name
        "url": "https://opensource.org/licenses/MIT" // License URL
      }
    },
    "tags": [
      {
        "name": "Template", // Tag name for categorizing operations
        "description": "Operations related to template" // Description of the tag
      }
    ],
    "servers": {
      "production": {
        "url": "%BASE_URL%%TF_VAR_API_VERSION%/%TF_VAR_API_SYSTEM_NAME%", // URL template for the production server
        "protocol": "wss" // WebSocket Secure protocol
      }
    }
};

// Function to read files and generate the AsyncAPI documentation
async function generateAsyncAPIDocument(baseDir = './src') {
    let channels = {}; // Initialize channels object to store channel definitions
    let components = {}; // Initialize components object to store component definitions

    // Recursive function to read files in a directory
    async function readFilesRecursively(dir) {
        const entries = await fs.promises.readdir(dir, { withFileTypes: true }); // Read directory entries
        for (const entry of entries) {
            const fullPath = path.join(dir, entry.name); // Construct full path of the entry
            if (entry.isDirectory()) {
                // If entry is a directory, recursively read its contents
                await readFilesRecursively(fullPath);
            } else if (entry.isFile() && entry.name.endsWith('.py')) {
                // If entry is a Python file, process it
                try {
                    const content = await fs.promises.readFile(fullPath, 'utf-8'); // Read file content
                    const asyncapiAnnotation = extractAsyncAPIAnnotation(content); // Extract AsyncAPI annotation
                    if (asyncapiAnnotation) {
                        const fileChannels = asyncapiAnnotation.channels; // Extract channels from annotation
                        if (fileChannels && Object.keys(fileChannels).length > 0) {
                            for (const channel of Object.keys(fileChannels)) {
                                // Merge channels into the main channels object
                                channels[channel] = {
                                    ...channels[channel],
                                    ...fileChannels[channel],
                                };
                            }
                        }
                        const fileComponents = asyncapiAnnotation.components; // Extract components from annotation
                        if (fileComponents) {
                            // Merge components into the main components object
                            components = {
                                ...components,
                                ...fileComponents,
                            };
                        }
                    }
                } catch (err) {
                    console.error(`Error reading file ${fullPath}:`, err); // Log error if file reading fails
                }
            }
        }
    }    

    // Function to extract AsyncAPI annotations from file content
    function extractAsyncAPIAnnotation(content) {
        const asyncapiRegex = /\/\*\*[\s\S]*?\*\//g; // Regex to match block comments
        const match = content.match(asyncapiRegex); // Find all block comments
        if (match) {
            const annotation = match[0]
                .replace(/\/\*\*|\*\//g, '') // Remove comment delimiters
                .replace(/\*/g, '') // Remove asterisks
                .replace('@asyncapi', '') // Remove @asyncapi tag
                .trim(); // Trim whitespace
            try {
                return yaml.load(annotation); // Parse YAML content
            } catch (error) {
                console.error(`Error parsing AsyncAPI annotation:`, error); // Log error if parsing fails
            }
        }
    }

    await readFilesRecursively(baseDir); // Start reading files from the base directory

    // Add missing message components that are referenced in channels
    if (!components.messages) {
        components.messages = {};
    }

    // Generate missing response messages
    const missingMessages = [
        'TemplateDeleteResponse',
        'TemplateGetResponse',
        'NewTemplateResponse',
        'TemplateUpdateResponse',
        'TemplateListResponse'
    ];

    missingMessages.forEach(messageName => {
        if (!components.messages[messageName]) {
            components.messages[messageName] = {
                messageId: messageName,
                contentType: "application/json",
                payload: {
                    type: "object",
                    properties: {
                        success: {
                            type: "boolean",
                            description: "Indicates if the operation was successful"
                        },
                        message: {
                            type: "string",
                            description: "Response message"
                        },
                        data: {
                            type: "object",
                            description: "Response data"
                        }
                    }
                }
            };
        }
    });

    let asyncAPIDocument = {
        ...asyncapiDefinition, // Spread the base AsyncAPI definition
        channels: channels, // Add channels to the AsyncAPI document
        components: components, // Add components to the AsyncAPI document
    };

    // Write the generated AsyncAPI document to a JSON file
    const outputPath = path.join(__dirname, '../api/asyncapi.json'); // Define output path
    try {
        await fs.promises.writeFile(outputPath, JSON.stringify(asyncAPIDocument, null, 2), 'utf-8'); // Write file
        console.log('Created asyncapi.json file successfully.'); // Log success message
    } catch (error) {
        console.error('Error writing asyncapi.json file:', error); // Log error if writing fails
    }
}

// Execute the AsyncAPI document generation
generateAsyncAPIDocument().catch((error) => {
    console.error('Error generating AsyncAPI document:', error); // Log error if generation fails
});