import { Component, OnInit, ViewChild, inject, signal, computed } from '@angular/core';
import { BreakpointObserver, Breakpoints } from '@angular/cdk/layout';
import { MatSidenav, MatSidenavModule } from '@angular/material/sidenav';
import { RouterOutlet } from '@angular/router';
import { AsyncPipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { SidebarComponent } from './sidebar/sidebar.component';
import { HeaderComponent } from './header/header.component';

/**
 * ShellComponent — Persistent authenticated layout wrapper.
 * Contains MatSidenav (sidebar), HeaderComponent, and <router-outlet>.
 * Responsive: sidenav is 'side' mode on desktop, 'over' mode on mobile.
 *
 * Design ref: US-047 DoD — sidebar navigation, header, content area
 */
@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [MatSidenavModule, RouterOutlet, AsyncPipe, SidebarComponent, HeaderComponent],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss',
})
export class ShellComponent implements OnInit {
  @ViewChild('sidenav') sidenav!: MatSidenav;

  private readonly breakpointObserver = inject(BreakpointObserver);

  /** True when viewport is mobile (≤ 768px). */
  readonly isMobile = signal(false);

  /** Sidenav mode: 'side' for desktop, 'over' for mobile. */
  readonly sidenavMode = computed(() => (this.isMobile() ? 'over' : 'side'));

  /** Sidenav open state: always open on desktop, closed by default on mobile. */
  readonly sidenavOpened = computed(() => !this.isMobile());

  ngOnInit(): void {
    this.breakpointObserver
      .observe([Breakpoints.Handset, Breakpoints.Tablet])
      .pipe(takeUntilDestroyed())
      .subscribe((result) => {
        this.isMobile.set(result.matches);
      });
  }

  onSidebarLinkClicked(): void {
    if (this.isMobile()) {
      this.sidenav.close();
    }
  }
}
