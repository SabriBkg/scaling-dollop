import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ROUTES } from "@/lib/constants";

/**
 * Root page — smart redirect based on auth state.
 * Server Component: can read httpOnly cookies directly.
 */
export default async function Home() {
  const cookieStore = await cookies();
  const hasToken = cookieStore.has("safenet_access");
  redirect(hasToken ? ROUTES.DASHBOARD : ROUTES.REGISTER);
}
