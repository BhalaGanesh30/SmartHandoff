import { inject } from '@angular/core';
import { CanActivateFn, ActivatedRouteSnapshot, Router } from '@angular/router';
import { AuthService } from './auth.service';

/**
 * Role Guard — enforces role-based access control on routes.
 *
 * Reads `data.roles: string[]` from the route definition.
 * Redirects unauthenticated users to /login.
 * Redirects authenticated users without required role to /403 (Forbidden).
 *
 * Usage in route config:
 *   {
 *     path: 'patients/:id/medications',
 *     canActivate: [roleGuard],
 *     data: { roles: ['pharmacist', 'physician'] },
 *     loadComponent: () => import(...),
 *   }
 */
export const roleGuard: CanActivateFn = (route: ActivatedRouteSnapshot) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const requiredRoles: string[] = route.data['roles'] ?? [];

  if (!auth.isAuthenticated()) {
    return router.parseUrl('/login');
  }

  const userRoles: string[] = auth.currentUser()?.role ? [auth.currentUser()!.role] : [];
  const hasRole = requiredRoles.length === 0 || requiredRoles.some((r) => userRoles.includes(r));

  if (!hasRole) {
    return router.parseUrl('/403');
  }

  return true;
};
