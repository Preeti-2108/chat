"""
/**
 * @openapi
 *
 * components:
 *   schemas:
 *     TemplatePython:
 *       type: object
 *       properties:
 *         id:
 *           type: string
 *           format: uuid
 *           description: Unique identifier for the template.
 *           example: 184CF8DA-B821-4FF4-BD6C-CDAFA166E2E0
 *         templateCompany:
 *           type: string
 *           description: Template company name.
 *           example: Company Name
 *         templateAgent:
 *           type: string
 *           description: Template agent name.
 *           example: Agent Name
 *         templateRootCause:
 *           type: string
 *           description: Template root cause.
 *           example: Root Cause
 *         templateAgentValidation:
 *           type: boolean
 *           description: Template agent validation.
 *           example: True
 *         templateIntentFailed:
 *           type: boolean
 *           description: Template intent failed.
 *           example: False
 *         isActive:
 *           type: boolean
 *           description: Is active or not.
 *           example: True
 *         templateActions:
 *           type: array
 *           items:
 *             type: object
 *             properties:
 *               templateActionsTimeStamp:
 *                 type: string
 *                 description: Timestamp of the action.
 *                 example: 1639172876
 *               templateActionsTag:
 *                 type: string
 *                 description: Tag of the action.
 *                 example: Tag Action 
 *         templateStatus:
 *           type: string
 *           description: Template status.
 *           example: Template Status
 *         createdBy:
 *           type: string
 *           description: Identification of the person who created the template.
 *           example: Firstname Lastname
 *         updatedBy:
 *           type: string
 *           description: Identification of the person who updted the template.
 *           example: Firstname Lastname
 *         createdAt:
 *           type: string
 *           format: date-time
 *           description: Date of creation of the template / date-time type.
 *           example: 2023-10-16T13:25:10.666Z
 *         updatedAt:
 *           type: string
 *           format: date-time
 *           description: Date of modification of the template / date-time type.
 *           example: 2023-10-16T13:28:40.028Z
 *     Success:
 *       properties:
 *         success:
 *           type: boolean
 *         message:
 *           type: string
 *         data:
 *           properties: {}
 *           type: object
 */
"""