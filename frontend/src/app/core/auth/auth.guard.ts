import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';
import { environment } from '../../../environments/environment';

/**
 * AuthGuard — protects routes that require an authenticated session.
 *
 * Checks AuthService.isAuthenticated() (computed signal that validates
 * JWT expiry). Redirects to /login if no valid token is present.
 *
 * DEV MODE: Set SKIP_AUTH=true in environment to bypass authentication for testing.
 *
 * Usage in route config:
 *   {
 *     path: 'dashboard',
 *     canActivate: [authGuard],
 *     loadComponent: () => import('../features/dashboard/dashboard.component')
 *       .then(m => m.DashboardComponent),
 *   }
 */
export const authGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  // DEV MODE: Skip authentication if SKIP_AUTH is enabled
  if ((environment as any).SKIP_AUTH === true) {
    console.warn('⚠️  AUTH GUARD BYPASSED - Development mode only!');
    return true;
  }

  if (authService.isAuthenticated()) {
    return true;
  }

  // Redirect to login; preserve the attempted URL for post-login redirect
  return router.createUrlTree(['/login'], {
    queryParams: { returnUrl: router.getCurrentNavigation()?.extractedUrl.toString() },
  });
};
