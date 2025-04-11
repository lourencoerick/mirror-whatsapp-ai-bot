"use client";
import React, { useEffect } from 'react';
import { useLayoutContext } from '@/contexts/layout-context';



export default function DashboardPage() {
  const { setPageTitle } = useLayoutContext();

  useEffect(() => {
    setPageTitle("Home");
  }, [setPageTitle]);

  return (
      <div>Conteúdo da dashboard aqui.</div>
  );
}
