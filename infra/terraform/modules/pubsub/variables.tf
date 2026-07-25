variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "environment" {
  type        = string
  description = "Deployment environment: dev | staging | prod"
}

variable "project_number" {
  type        = string
  description = "Numeric GCP project number (from cloud_run module output or data.google_project)"
}

variable "hl7_listener_sa" {
  type        = string
  description = "Email of the HL7 Listener Cloud Run service account (publisher on adt-events)"
}

variable "agent_service_accounts" {
  type        = map(string)
  description = "Map of agent service name \u2192 service account email (from cloud_run module output)"
}variable "coordinator_sub_ack_deadline_seconds" {
  description = "ACK deadline in seconds for the coordinator-sub subscription"
  type        = number
  default     = 60
}

variable "coordinator_dlq_max_delivery_attempts" {
  description = "Number of delivery attempts before a message is sent to coordinator-dlq"
  type        = number
  default     = 5
}

variable "alert_notification_channels" {
  description = "List of Cloud Monitoring notification channel IDs for DLQ alerts"
  type        = list(string)
  default     = []
}