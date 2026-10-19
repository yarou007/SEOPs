// Local-only TLS termination. Next remains on HTTP for same-origin SSR fetches.
import https from "node:https";
import http from "node:http";
import net from "node:net";
import { readFileSync } from "node:fs";
import { parseArgs } from "node:util";

const { values } = parseArgs({ options: {
  key: { type: "string", default: ".certs/key.pem" }, cert: { type: "string", default: ".certs/cert.pem" },
  port: { type: "string", default: "3443" }, target: { type: "string", default: "3000" },
} });
const target = Number(values.target);
const server = https.createServer({ key: readFileSync(values.key), cert: readFileSync(values.cert) }, (req, res) => {
  const upstream = http.request({ hostname: "127.0.0.1", port: target, path: req.url, method: req.method,
    headers: { ...req.headers, "x-forwarded-proto": "https" } }, incoming => {
    res.writeHead(incoming.statusCode ?? 502, incoming.headers); incoming.pipe(res);
  });
  upstream.on("error", () => { if (!res.headersSent) res.writeHead(502); res.end("Next.js is unavailable"); });
  req.pipe(upstream);
});
server.on("upgrade", (req, socket, head) => {
  const upstream = net.connect(target, "127.0.0.1", () => {
    upstream.write(`${req.method} ${req.url} HTTP/${req.httpVersion}\r\n`);
    for (let i = 0; i < req.rawHeaders.length; i += 2) upstream.write(`${req.rawHeaders[i]}: ${req.rawHeaders[i + 1]}\r\n`);
    upstream.write("\r\n"); if (head.length) upstream.write(head);
    socket.pipe(upstream).pipe(socket);
  });
  upstream.on("error", () => socket.destroy()); socket.on("error", () => upstream.destroy());
});
server.listen(Number(values.port), "127.0.0.1", () => console.log(`Local HTTPS: https://localhost:${values.port} → http://127.0.0.1:${target}`));
