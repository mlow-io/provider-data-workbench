// A machine-readable ready message must not depend on Vite's colored CLI banner.
import { createServer } from 'vite';

const server = await createServer({ server: { host: '127.0.0.1', port: 0, strictPort: true } });
await server.listen();
const address = server.httpServer?.address();
if (!address || typeof address === 'string') {
  await server.close();
  throw new Error('Owned frontend requires a TCP listener');
}
console.log(`PDTL_OPERATIONS_FRONTEND_URL=http://127.0.0.1:${address.port}`);
