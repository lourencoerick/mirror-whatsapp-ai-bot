"use client";  // Necessário no App Router para usar hooks/eventos no client
import { useState } from "react";
import { signIn } from "next-auth/react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function LoginPage() {
  // Estados locais para armazenar e-mail e senha
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // Função de envio do formulário de login
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Chama o NextAuth para fazer signIn com o provider de credenciais
    // (Certifique-se de ter configurado CredentialsProvider no NextAuth)
    const result = await signIn("credentials", {
      redirect: true,        // redireciona após login (ou use false para tratar manualmente)
      email,                 // campos enviados para o provider de credencial
      password,
      callbackUrl: "/",      // para onde redirecionar após login bem-sucedido
    });
    // Opcional: tratar result.error para exibir erros de login, se necessário.
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      {/* Container do card de login */}
      <div className="w-full max-w-sm p-6 bg-white rounded-lg shadow">
        <h1 className="text-2xl font-bold text-center mb-4">Entrar</h1>
        {/* Formulário de login */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="email">E-mail</Label>
            <Input 
              type="email" 
              id="email" 
              placeholder="seuemail@dominio.com" 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required 
            />
          </div>
          <div>
            <Label htmlFor="password">Senha</Label>
            <Input 
              type="password" 
              id="password" 
              placeholder="sua senha" 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required 
            />
          </div>
          <Button type="submit" className="w-full">Entrar</Button>
        </form>

        {/* Separador */}
        <div className="flex items-center my-4">
          <span className="w-full border-b border-gray-300"></span>
          <span className="px-2 text-sm text-gray-600">ou</span>
          <span className="w-full border-b border-gray-300"></span>
        </div>

        {/* Botões de login social */}
        <Button 
          type="button" 
          variant="outline" 
          className="w-full mb-2" 
          onClick={() => signIn("google")}
        >
          Entrar com Google
        </Button>
        <Button 
          type="button" 
          variant="outline" 
          className="w-full" 
          onClick={() => signIn("facebook")}
        >
          Entrar com Facebook
        </Button>

        {/* Link para criar conta */}
        <p className="mt-4 text-center text-sm text-gray-600">
          Não tem uma conta?{" "}
          <Link href="/register" className="font-medium text-blue-600 hover:underline">
            Criar Conta
          </Link>
        </p>
      </div>
    </div>
  );
}
