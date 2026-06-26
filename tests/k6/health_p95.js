import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "https://queue-storm-qbfrm.ondigitalocean.app";

export const options = {
  scenarios: {
    health_p95_latency: {
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
  const res = http.get(`${BASE_URL}/health`, { timeout: "30s" });

  check(res, {
    "health status is 200": (r) => r.status === 200,
    "health is json": (r) =>
      (r.headers["Content-Type"] || "").includes("application/json"),
    "health body is ok": (r) => {
      try {
        return r.json("status") === "ok";
      } catch {
        return false;
      }
    },
  });

  sleep(1);
}
