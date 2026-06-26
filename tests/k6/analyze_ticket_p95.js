import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "https://queue-storm-qbfrm.ondigitalocean.app";
const payload = open(__ENV.SAMPLE_FILE || "../../samples/sample_request.json");

function doesNotRequestUnsafeCredentials(body) {
  const text = (body || "").toLowerCase();
  const protectiveWarning =
    /(do not|don't|never)\s+(share|send|provide|enter|tell|give).{0,60}(otp|pin|password|cvv|full card number)/i;
  const credentialRequest =
    /(share|send|provide|enter|tell|give).{0,60}(otp|pin|password|cvv|full card number)/i;

  return protectiveWarning.test(text) || !credentialRequest.test(text);
}

export const options = {
  scenarios: {
    analyze_ticket_p95_latency: {
      executor: "ramping-vus",
      stages: [
        { duration: "15s", target: 1 },
        { duration: "30s", target: 3 },
        { duration: "1m", target: 8 },
        { duration: "15s", target: 0 },
      ],
      gracefulRampDown: "10s",
    },
  },
  thresholds: {
    checks: ["rate==1.0"],
    http_req_failed: ["rate==0"],
    http_req_duration: ["p(95)<5000", "p(99)<15000"],
  },
};

export default function () {
  const res = http.post(`${BASE_URL}/analyze-ticket`, payload, {
    headers: { "Content-Type": "application/json" },
    timeout: "30s",
  });

  check(res, {
    "analyze status is 2xx": (r) => r.status >= 200 && r.status < 300,
    "analyze is json": (r) =>
      (r.headers["Content-Type"] || "").includes("application/json"),
    "analyze has valid json": (r) => {
      try {
        r.json();
        return true;
      } catch {
        return false;
      }
    },
    "analyze does not ask for unsafe credentials": (r) =>
      doesNotRequestUnsafeCredentials(r.body),
    "analyze does not expose internals": (r) =>
      !/(traceback|stack trace|api[_-]?key|secret|token)/i.test(r.body || ""),
  });

  sleep(1);
}
