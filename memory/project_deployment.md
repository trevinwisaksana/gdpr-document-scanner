---
name: project-deployment
description: Deployed Cloud Run base URL for the GDPR document scanner app
metadata:
  type: project
---

The production app is deployed on Cloud Run at:
https://dashboard-http-95861934207.us-central1.run.app

**Why:** This is the live deployment URL used for API calls and UI access.
**How to apply:** Use this as `API_BASE_URL` when referencing the deployed app, testing endpoints, or configuring environment variables.
