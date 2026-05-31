import React from 'react';
import { Outlet } from 'react-router-dom';
import Layout from './Layout';
import SessionIdleGuard from '../Auth/SessionIdleGuard';

/** Persistent shell — sidebar stays mounted while route content swaps. */
export default function AppLayout() {
  return (
    <Layout>
      <SessionIdleGuard />
      <Outlet />
    </Layout>
  );
}
