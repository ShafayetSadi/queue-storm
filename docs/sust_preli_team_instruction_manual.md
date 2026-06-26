# bKash presents SUST CSE Carnival 2026: Codex Community Hackathon

## Team Instructions Manual

**Challenge:** AI/API Challenge  
**Round:** 4-Hour Online Preliminary

---

## Read This First

This manual explains how to execute the preliminary round:

- Read the problem statement
- Divide work among teammates
- Build the API
- Test the API
- Deploy the API
- Submit the required deliverables

It should be read together with the **Problem Statement** and the **Evaluation Rubric**.

---

## 1. Participant Document Pack

| Document                 | Purpose                                                                           | What it Answers               |
| ------------------------ | --------------------------------------------------------------------------------- | ----------------------------- |
| Problem Statement        | Defines the challenge, input/output schema, and required behaviour.               | What do we need to build?     |
| Evaluation Rubric        | Explains scoring categories, safety penalties, hidden tests, and tie-breakers.    | How will we be judged?        |
| Team Instructions Manual | Explains build flow, deployment options, secrets policy, testing, and submission. | How do we execute and submit? |

---

## 2. What Teams Need to Build

| Required Item          | Instruction                                                                                              |
| ---------------------- | -------------------------------------------------------------------------------------------------------- |
| API Service            | Build a backend service for the preliminary challenge API.                                               |
| `GET /health`          | Must return `{"status":"ok"}` to prove the service is running.                                           |
| Main Analysis Endpoint | Accept required input JSON and return the exact structured output JSON defined in the Problem Statement. |
| Valid JSON Response    | Use the exact required field names, data types, and enum values.                                         |
| `README.md`            | Explain setup, run command, AI/model usage, safety logic, and known limitations.                         |

> **Frontend/UI is optional**
>
> A frontend is **not required** and will **not be directly judged**.
>
> Prioritize:
>
> - API correctness
> - Reasoning quality
> - Safety
> - Reliability
> - Deployment
> - Documentation

---

## 3. Available Resources

| Resource                 | Usage                                                                       |
| ------------------------ | --------------------------------------------------------------------------- |
| Poridhi Labs             | Coding, testing, deployment support                                         |
| Poridhi VM               | Manual deployment environment                                               |
| AWS through Poridhi Labs | Deploy using AWS resources provided through Poridhi Labs                    |
| Puku Editor / CLI        | AI-assisted coding, debugging, setup, refactoring, documentation            |
| Any Other Platform       | Render, Railway, Fly.io, Vercel, AWS EC2, or any reachable hosting platform |

> **Resource Policy**
>
> Poridhi resources are **support**, not a restriction.
>
> Teams may deploy anywhere as long as the submitted API is reachable.

---

## 4. Suggested Team Role Split

| Role                    | Responsibility                                                          |
| ----------------------- | ----------------------------------------------------------------------- |
| API / Backend Lead      | Endpoints, validation, request parsing, response formatting, deployment |
| Reasoning / Logic Lead  | Core decision logic, routing, prioritization, evidence matching         |
| AI / Safety / Docs Lead | LLM integration, safety guardrails, edge-case testing, README           |

> **Solo teams**
>
> Follow this order:
>
> 1. Schema
> 2. Reasoning
> 3. Safety
> 4. Deployment

---

## 5. API Submission Rule

The submitted base URL should expose:

```text
GET  https://your-service-url.com/health
POST https://your-service-url.com/[main-endpoint]
```

Requirements:

- No login required
- No dashboard access
- No manual approval
- No VPN/private network
- Accept JSON input
- Return JSON output
- Use official endpoint names
- Keep the service online during judging

---

## 6. Deployment Options

| Priority | Submission Path           | Submit                                                | Notes                                       |
| -------- | ------------------------- | ----------------------------------------------------- | ------------------------------------------- |
| 1        | Working Endpoint URL      | Public URL + GitHub repository                        | Preferred                                   |
| 2        | Docker Fallback           | Dockerfile/image details + dependencies + run command | Used if public deployment isn't available   |
| 3        | Code-only Reproducibility | GitHub repository with complete setup instructions    | Lowest deployment score if difficult to run |

---

## 7. Deploying on Poridhi Lab / VM / AWS

- Verify the API works locally first.
- Deploy to Poridhi Lab, VM, or AWS if available.
- Install dependencies.
- Store secrets as environment variables.
- Bind the service to `0.0.0.0`.
- Expose the service through the platform URL or public IP.
- Test both `/health` and the main endpoint externally before submission.

---

## 8. Docker Fallback Rules

| Rule                   | Requirement                              |
| ---------------------- | ---------------------------------------- |
| Recommended Image Size | Under **500 MB**                         |
| Hard Image Limit       | **1 GB**                                 |
| GPU                    | Not allowed                              |
| Large Local Models     | Not allowed                              |
| Multi-GB Downloads     | Not allowed                              |
| Runtime Training       | Not allowed                              |
| Port Binding           | Bind to `0.0.0.0`                        |
| Health Check           | `/health` must respond within 60 seconds |
| Secrets                | Environment variables only               |

Example:

```bash
docker build -t hackathon-team .
docker run -p 8000:8000 --env-file judging.env hackathon-team
```

---

## 9. AI and Model Usage Policy

| Approach                         | Status                             |
| -------------------------------- | ---------------------------------- |
| Rule-based Logic                 | ✅ Allowed and encouraged          |
| External AI APIs                 | ✅ Allowed using your own API keys |
| Lightweight Local Models         | ✅ Allowed (CPU only)              |
| Hybrid Rule + AI                 | ✅ Recommended                     |
| Huge Local LLMs / GPU Dependency | ❌ Not allowed                     |

> **Third-party API Responsibility**
>
> Teams are responsible for:
>
> - API keys
> - Cost
> - Rate limits
> - Availability

Organizers will **not** provide third-party API keys.

---

## 10. Secrets and Environment Variables

## Important Security Rule

Never commit real secrets to GitHub.

Do **not** place secrets in:

- README
- Docker images
- Commit history
- Screenshots
- Public messages

### Where Secrets Belong

| Location                        | Content                                              |
| ------------------------------- | ---------------------------------------------------- |
| GitHub Repository               | Source code, README, Dockerfile, `.env.example` only |
| `.env.example`                  | Variable names only                                  |
| Hosting Platform                | Real deployment secrets                              |
| Submission Form (Private Field) | Secrets required for Docker/code judging             |

Repository example:

```text
OPENAI_API_KEY=
MODEL_NAME=
PORT=8000
```

Private judging example:

```text
OPENAI_API_KEY=your_real_temporary_key
MODEL_NAME=your_model_name
PORT=8000
```

Recommendations:

- Use temporary keys.
- Rotate keys after judging.
- Missing required secrets may reduce deployment scores.

---

## 11. Repository Access Policy

| Repository Type | Requirement                                    |
| --------------- | ---------------------------------------------- |
| Public          | Submit repository URL                          |
| Private         | Add organizer GitHub accounts with read access |
| Availability    | Keep accessible until preliminary results      |
| After Results   | May archive or make private                    |
| Secrets         | Never commit real secrets                      |

---

## 12. Testing Checklist Before Submission

| Check                                 | Required |
| ------------------------------------- | :------: |
| `/health` returns `{"status":"ok"}`   |    ✅    |
| Main endpoint accepts sample JSON     |    ✅    |
| Response contains all required fields |    ✅    |
| Enum values match specification       |    ✅    |
| Handles empty optional input safely   |    ✅    |
| Handles malformed input safely        |    ✅    |
| Never asks for sensitive credentials  |    ✅    |
| Never promises unauthorized actions   |    ✅    |
| Responds within timeout               |    ✅    |
| README complete                       |    ✅    |

---

## 13. Submission Form Checklist

| Field                      |   Required    | Notes                                  |
| -------------------------- | :-----------: | -------------------------------------- |
| Team Name & Team ID        |      ✅       | Registered information                 |
| GitHub Repository URL      |      ✅       | Public or organizer-accessible private |
| Submission Path            |      ✅       | Endpoint, Docker, or code-only         |
| Public Endpoint URL        | If applicable | Example: `https://team.example.com`    |
| Docker Build/Run Command   |   If Docker   | Include port and env-file              |
| Environment Variable Names | If applicable | Names only                             |
| Secrets for Judging        |   If needed   | Private field only                     |
| Sample Request & Response  |      ✅       | README or separate file                |
| AI/Model Usage             |      ✅       | Describe approach                      |
| Safety Logic               |      ✅       | Explain safeguards                     |
| Known Limitations          |      ✅       | Be honest                              |
| No Real Customer Data      |      ✅       | Synthetic data only                    |
| No Secrets Committed       |      ✅       | Confirmation                           |

---

## 14. What Not to Do

| Do Not                               | Why                              |
| ------------------------------------ | -------------------------------- |
| Build only a UI                      | API is evaluated                 |
| Require login                        | Judge must call API directly     |
| Use real customer or production data | Privacy & safety                 |
| Trigger production APIs              | Out of scope                     |
| Ask for passwords, OTPs, or secrets  | Critical safety violation        |
| Promise unauthorized actions         | System is only a support copilot |
| Commit API keys                      | Security risk                    |
| Depend on huge GPU models            | Not judgeable                    |

---

## 15. Common Troubleshooting

| Problem                                 | What to Check                                    |
| --------------------------------------- | ------------------------------------------------ |
| 404 on `/health`                        | Route names and base URL                         |
| Invalid JSON                            | Proper `application/json` response               |
| Schema errors                           | Required fields, enums, null handling            |
| Timeout                                 | Reduce model calls, cache safely, fallback logic |
| External API failure                    | Handle quota/rate limits gracefully              |
| Docker works locally but not for judges | Bind to `0.0.0.0`, expose correct port           |
| Private repo inaccessible               | Add organizer accounts                           |
| Missing secrets                         | Configure environment variables correctly        |

---

## 16. Final Pre-Submit Checklist

- [ ] Problem statement implemented correctly
- [ ] `/health` tested
- [ ] Main endpoint tested
- [ ] Safety guardrails verified
- [ ] Deployment or Docker fallback prepared
- [ ] Repository accessible
- [ ] README completed
- [ ] `.env.example` included (if needed)
- [ ] No secrets committed
- [ ] Required private secrets submitted
- [ ] Submission completed before deadline

---

## Final Advice

> Build the API first.
>
> Make the schema correct.
>
> Add robust reasoning and decision logic.
>
> Add safety guardrails.
>
> Test thoroughly.
>
> Deploy reliably.
>
> Submit clearly.
>
> **A simple, reliable, safe API will score better than a flashy but broken product.**
