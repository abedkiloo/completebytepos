import React from 'react';
import { Outlet } from 'react-router-dom';
import Layout from './Layout';

/** Persistent shell — sidebar stays mounted while route content swaps. */
export default function AppLayout() {
  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}
