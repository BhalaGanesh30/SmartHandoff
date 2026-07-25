# ── Topics ───────────────────────────────────────────────────────────────
resource "google_pubsub_topic" "adt_events" {
  name    = "adt-events-${var.environment}"
  project = var.project_id

  # Message ordering is enforced per-subscription via ordering_key, not at the topic level.
  message_retention_duration = "604800s" # 7-day replay window for audit / re-processing
}

resource "google_pubsub_topic" "adt_events_dlq" {
  name                       = "adt-events-dlq-${var.environment}"
  project                    = var.project_id
  message_retention_duration = "604800s"
}

resource "google_pubsub_topic" "notification_requests" {
  name                       = "notification-requests-${var.environment}"
  project                    = var.project_id
  message_retention_duration = "86400s" # 24-hour retention sufficient for notifications
}

resource "google_pubsub_topic" "notification_dlq" {
  name    = "notification-requests-dlq-${var.environment}"
  project = var.project_id
}

# ── Per-agent subscriptions ────────────────────────────────────────────────
locals {
  # Maps subscription name → agent service name (used to look up the SA in iam.tf)
  agent_subscriptions = {
    "docs-agent-sub"  = "docs-agent"
    "medrecon-sub"    = "medrecon-agent"
    "bed-mgmt-sub"    = "bed-mgmt-agent"
    "followup-sub"    = "followup-agent"
    "comms-sub"       = "comms-agent"
  }
}

resource "google_pubsub_subscription" "agent_subs" {
  for_each = local.agent_subscriptions

  name    = "${each.key}-${var.environment}"
  topic   = google_pubsub_topic.adt_events.id
  project = var.project_id

  # Ordering enforced per-message via ordering_key set by the HL7 Listener publisher.
  enable_message_ordering = true

  ack_deadline_seconds       = 60 # Agents have 60 s to process and ack
  message_retention_duration = "604800s"
  retain_acked_messages      = false

  expiration_policy {
    ttl = "" # Never expire the subscription itself
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.adt_events_dlq.id
    max_delivery_attempts = 5 # TR-015: DLQ after 5 failures (6 total attempts)
  }
  # Note: flow_control (max_outstanding_messages = 100, max_outstanding_bytes = 100MB)
  # is configured on the Pub/Sub client SDK side, not in Terraform.
  # See services/shared/pubsub_client.py for the subscriber flow control settings.
}

# ── Notification subscription ───────────────────────────────────────────────
resource "google_pubsub_subscription" "notification_sub" {
  name    = "notification-sub-${var.environment}"
  topic   = google_pubsub_topic.notification_requests.id
  project = var.project_id

  ack_deadline_seconds       = 30
  message_retention_duration = "86400s"

  expiration_policy {
    ttl = ""
  }

  retry_policy {
    minimum_backoff = "5s"
    maximum_backoff = "60s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.notification_dlq.id
    max_delivery_attempts = 5
  }
}

# ── Coordinator-specific DLQ setup ──────────────────────────────────────────

# coordinator-dlq topic — receives messages after max_delivery_attempts
resource "google_pubsub_topic" "coordinator_dlq" {
  name    = "coordinator-dlq-${var.environment}"
  project = var.project_id

  labels = {
    environment = var.environment
    component   = "coordinator-agent"
    managed_by  = "terraform"
  }
}

# coordinator-sub — primary subscription with dedicated dead-letter policy
resource "google_pubsub_subscription" "coordinator_sub" {
  name    = "coordinator-sub-${var.environment}"
  topic   = google_pubsub_topic.adt_events.id
  project = var.project_id

  enable_message_ordering    = true
  ack_deadline_seconds       = var.coordinator_sub_ack_deadline_seconds
  message_retention_duration = "604800s"
  retain_acked_messages      = false

  expiration_policy {
    ttl = ""
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.coordinator_dlq.id
    max_delivery_attempts = var.coordinator_dlq_max_delivery_attempts
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }

  labels = {
    environment = var.environment
    component   = "coordinator-agent"
    managed_by  = "terraform"
  }
}

# coordinator-dlq-sub — pull subscription for DLQ inspection / replay
resource "google_pubsub_subscription" "coordinator_dlq_sub" {
  name    = "coordinator-dlq-sub-${var.environment}"
  topic   = google_pubsub_topic.coordinator_dlq.id
  project = var.project_id

  ack_deadline_seconds = 600 # Extended for manual review

  labels = {
    environment = var.environment
    component   = "coordinator-agent-dlq"
    managed_by  = "terraform"
  }
}

# ── IAM for DLQ dead-lettering ─────────────────────────────────────────────

# Required by GCP: Pub/Sub service account must publish to DLQ topic
data "google_project" "current" {
  project_id = var.project_id
}

resource "google_pubsub_topic_iam_member" "coordinator_dlq_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.coordinator_dlq.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription_iam_member" "coordinator_sub_subscriber" {
  project      = var.project_id
  subscription = google_pubsub_subscription.coordinator_sub.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# ── Cloud Monitoring alert ──────────────────────────────────────────────────

# Alert fires when coordinator-dlq-sub backlog > 0
resource "google_monitoring_alert_policy" "coordinator_dlq_alert" {
  display_name = "Coordinator DLQ — Unprocessed Messages (${var.environment})"
  project      = var.project_id
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "coordinator-dlq-sub backlog > 0"

    condition_threshold {
      filter = join(" AND ", [
        "resource.type=\"pubsub_subscription\"",
        "resource.labels.subscription_id=\"coordinator-dlq-sub-${var.environment}\"",
        "metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\""
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  notification_channels = var.alert_notification_channels

  documentation {
    content = <<-EOT
      ## Coordinator DLQ Alert

      One or more ADT events have failed processing after ${var.coordinator_dlq_max_delivery_attempts} delivery attempts
      and have been moved to `coordinator-dlq-sub-${var.environment}`.

      **Immediate actions:**
      1. Check coordinator-agent Cloud Run logs for the failed `encounter_id`
      2. Inspect the DLQ message: `gcloud pubsub subscriptions pull coordinator-dlq-sub-${var.environment} --auto-ack --limit=1`
      3. Identify root cause (DB unavailable, schema mismatch, etc.)
      4. After fix, replay the message to `adt-events-${var.environment}` topic

      **Runbook:** https://wiki.internal/smarthandoff/runbooks/coordinator-dlq
    EOT
    mime_type = "text/markdown"
  }

  labels = {
    environment = var.environment
    severity    = "critical"
  }
}
