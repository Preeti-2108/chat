"""
/**
 * @asyncapi
 * components:
 *   messages:
 *     NewTemplateSampleResponse:
 *       messageId: newTemplateSampleResponse
 *       contentType: application/json
 *       payload:
 *         $ref: '#/components/schemas/TemplateSample'
 *     TemplateSampleUpdateResponse:
 *       messageId: templateSampleUpdateResponse
 *       contentType: application/json
 *       payload:
 *         $ref: '#/components/schemas/TemplateSample'
 *     TemplateSampleRetrievalResponse:
 *       messageId: templateSampleRetrievalResponse
 *       contentType: application/json
 *       payload:
 *         $ref: '#/components/schemas/TemplateSample'
 *     TemplateSampleDeletionResponse:
 *       messageId: templateSampleDeletionResponse
 *       contentType: application/json
 *       payload:
 *         $ref: '#/components/schemas/TemplateSample'
 *     TemplateSampleListResponse:
 *       messageId: templateSampleListResponse
 *       contentType: application/json
 *       payload:
 *         $ref: '#/components/schemas/TemplateSample'
 *   schemas:
 *     TemplateSample:
 *       type: object
 *       properties:
 *         id:
 *           type: string
 *           format: uuid
 *           description: Unique identifier for the template sample.
 *           example: 184CF8DA-B821-4FF4-BD6C-CDAFA166E2E0
 *         templateSampleCompany:
 *           type: string
 *           description: Template sample company name.
 *           example: Company Name
 *         templateSampleAgent:
 *           type: string
 *           description: Template sample agent name.
 *           example: Agent Name
 *         templateSampleRootCause:
 *           type: string
 *           description: Template sample root cause.
 *           example: Root Cause
 *         templateSampleAgentValidation:
 *           type: boolean
 *           description: Template sample agent validation.
 *           example: true
 *         templateSampleIntentFailed:
 *           type: boolean
 *           description: Template sample intent failed.
 *           example: false
 *         isActive:
 *           type: boolean
 *           description: Is active or not.
 *           example: true
 *         templateSampleActions:
 *           type: array
 *           items:
 *             type: object
 *             properties:
 *               templateSampleActionsTimeStamp:
 *                 type: string
 *                 description: Timestamp of the action.
 *                 example: 1639172876
 *               templateSampleActionsTag:
 *                 type: string
 *                 description: Tag of the action.
 *                 example: Tag Action
 *         templateSampleStatus:
 *           type: string
 *           description: Template sample status.
 *           example: Template sample Status
 *         createdBy:
 *           type: string
 *           description: Identification of the person who created the template sample.
 *           example: Firstname Lastname
 *         updatedBy:
 *           type: string
 *           description: Identification of the person who updated the template sample.
 *           example: Firstname Lastname
 *         createdAt:
 *           type: string
 *           format: date-time
 *           description: Date of creation of the template sample / date-time type.
 *           example: 2023-10-16T13:25:10.666Z
 *         updatedAt:
 *           type: string
 *           format: date-time
 *           description: Date of modification of the template sample / date-time type.
 *           example: 2023-10-16T13:28:40.028Z
 */
"""