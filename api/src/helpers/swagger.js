const fs = require('fs');
const swaggerJSDoc = require('swagger-jsdoc');

const serverProd = {
	url: process.env.BACKEND_ENDPOINT,
	description: 'Production server',
};

const servers = [
	serverProd,
	// serverDev,
];

servers.forEach((server, index) => {
	const swaggerDefinition = {
		openapi: '3.0.0',
		info: {
			title: 'Python Template CDK', // To customize
			version: '1.0.0', // To customize
			description: 'The Python Template APIs is a collection of APIs calls that deal with system objects in the Agent Augemented system.', // To customize
			termsOfService: 'https://www.soprasteria.com/footer/terms-of-use',
			contact: {
				email: 'support.dps.fr.api.contact@soprasteria.com',
			},
		}
	};

	const options = {
		swaggerDefinition,
		apis: ['./**/**/*.py'],
	};

	const output = JSON.stringify(swaggerJSDoc(options), null, 2);
	fs.writeFileSync('src/api/swagger.json', output);
	process.stdout.write('Created swagger.json file successfully.\n');
});
