import { auth } from "@clerk/nextjs/server";
import {

  SignInButton,
  SignUpButton,
  SignedIn,
  SignedOut,
  UserButton,
} from '@clerk/nextjs'

export default async function Home() {
  const authResult = await auth();
  const token = await authResult.getToken();

  console.log(token);

  return (
    <header className="flex justify-end items-center p-4 gap-4 h-16">
      <SignedOut>
        <SignInButton />
        <SignUpButton />
      </SignedOut>
      <SignedIn>
        <UserButton />
      </SignedIn>
    </header>

  );
}