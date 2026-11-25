// Cloudflare Pages Function: /api/ladder
// Bi-weekly 4.0+ Open Play ladder — sessions, roster, match submit, standings.

import { handleLadderRequest } from '../../lib/ladder-api.js';

export async function onRequest(context) {
  const { request, env } = context;

  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Max-Age': '86400'
  };

  return handleLadderRequest(request, env, corsHeaders);
}
