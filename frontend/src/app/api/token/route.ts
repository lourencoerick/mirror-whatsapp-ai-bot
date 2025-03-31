import { NextResponse } from 'next/server';
import { auth } from '@clerk/nextjs/server';
import { log } from 'next-axiom';

export async function GET() {
  try {
    const { userId, getToken } = await auth(); // Get server-side auth helpers

    if (!userId) {
      // If userId is null, the user is not signed in or session is invalid
      log.warn("[API Token Route] Unauthorized access attempt.");
      return new NextResponse(JSON.stringify({ error: 'Unauthorized' }), {
         status: 401,
         headers: { 'Content-Type': 'application/json' }
        });
    }

    // You can specify a template if you have custom JWT templates configured in Clerk
    const token = await getToken({ template: "fastapi-backend" });
  

    if (!token) {
      // This is less likely if userId exists, but handle defensively
      log.error("[API Token Route] Could not generate token even though userId exists.", { userId });
      return new NextResponse(JSON.stringify({ error: 'Could not generate token' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
       });
    }

    // Return the token successfully
    return NextResponse.json({ token });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } catch (error: any) {
    log.error("[API Token Route] Internal Server Error:", { error: error.message });
    console.error('[API TOKEN ROUTE] Error:', error); // Log server-side
    return new NextResponse(JSON.stringify({ error: 'Internal Server Error' }), {
       status: 500,
       headers: { 'Content-Type': 'application/json' }
      });
  }
}