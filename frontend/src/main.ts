import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { Component } from '@angular/core';

@Component({
  selector: 'app-root',
  standalone: true,
  template: '<router-outlet></router-outlet>',
})
export class AppComponent {}

bootstrapApplication(AppComponent, appConfig)
  .catch((err) => console.error(err));
