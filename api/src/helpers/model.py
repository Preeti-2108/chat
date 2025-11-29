"""
/**
 * @asyncapi
 * components:
 *   messages:
 *     CreateResponse:
 *       messageId: createResponse
 *       contentType: application/json
 *       payload:
 *         $ref: '#/components/schemas/CHATINTERNAL'
 *     chatUpdateResponse:
 *       messageId: chatUpdateResponse
 *       contentType: application/json
 *       payload:
 *         $ref: '#/components/schemas/CHATINTERNAL'
 *     chatGetResponse:
 *       messageId: chatGetResponse
 *       contentType: application/json
 *       payload:
 *         $ref: '#/components/schemas/CHATINTERNAL'
 *     chatGetAssistantResponse:
 *       messageId: chatGetAssistantResponse
 *       contentType: application/json
 *       payload:
 *         $ref: '#/components/schemas/CHATINTERNAL'
 *     chatDeleteResponse:
 *       messageId: chatDeleteResponse
 *       contentType: application/json
 *       payload:
 *         $ref: '#/components/schemas/CHATINTERNAL'
 *   schemas:
 *     CHATINTERNAL:
 *       type: object
 *       properties:
 *         success:
 *           type: boolean
 *           description: Indicates whether the request was successful or not.
 *           example: true
 *         message:
 *           type: string
 *           description: A message describing the result of the chat conversation.
 *           example: "Chat conversation successful."
 *         data:
 *           type: object
 *           properties:
 *             content:
 *               type: string
 */
"""