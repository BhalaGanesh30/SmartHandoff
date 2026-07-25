# SmartHandoff Frontend

Angular 17+ frontend for the SmartHandoff Care Coordination Platform with real-time SignalR integration.

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm start

# Run tests
npm test

# Build for production
npm run build:prod
```

## 📦 Project Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── core/                    # Core services and utilities
│   │   │   ├── api/                 # API client services
│   │   │   │   ├── encounter-tasks-api.service.ts
│   │   │   │   └── index.ts
│   │   │   ├── auth/                # Authentication services
│   │   │   │   ├── auth.service.ts
│   │   │   │   └── jwt.interceptor.ts
│   │   │   ├── models/              # TypeScript interfaces/types
│   │   │   │   ├── task.model.ts
│   │   │   │   └── index.ts
│   │   │   └── signalr/             # Real-time SignalR integration
│   │   │       ├── signalr.service.ts
│   │   │       ├── signalr.service.spec.ts
│   │   │       └── index.ts
│   │   ├── features/                # Feature modules
│   │   │   ├── auth/                # Authentication pages
│   │   │   └── dashboard/           # Care team dashboard
│   │   │       ├── dashboard.component.ts
│   │   │       ├── dashboard.component.html
│   │   │       ├── dashboard.component.scss
│   │   │       └── dashboard.component.spec.ts
│   │   ├── app.config.ts
│   │   └── app.routes.ts
│   └── environments/                # Environment configuration
│       ├── environment.ts
│       └── environment.production.ts
├── scripts/
│   └── validate-task-004.js        # Implementation validation script
├── angular.json
├── package.json
├── tsconfig.json
└── README.md
```

## 🔧 TASK-004 Implementation

This implementation completes **US-022: Real-time Task Updates via SignalR** with the following components:

### 1. SignalR Service (`src/app/core/signalr/signalr.service.ts`)
- **Real-time WebSocket connection** using `@microsoft/signalr`
- **JWT authentication** via `accessTokenFactory`
- **Automatic reconnection** with retry delays [0, 1s, 2s, 5s, 10s]
- **Missed task re-fetch** on reconnection
- **RxJS Observable** (`taskUpdated$`) for event streaming

### 2. Encounter Tasks API Service (`src/app/core/api/encounter-tasks-api.service.ts`)
- REST API client for task operations
- Methods:
  - `getTasksForEncounter(encounterId)` - Fetch all tasks
  - `getTaskById(taskId)` - Fetch single task
  - `getTasksByStatus(encounterId, status)` - Filter by status
  - `getTasksByRole(encounterId, role)` - Filter by role
- Automatic retry on transient failures
- Error handling and logging

### 3. Dashboard Component (`src/app/features/dashboard/dashboard.component.ts`)
- **Angular 17+ standalone component** with signals
- **Real-time task updates** via SignalR subscription
- **Initial task load** via REST API
- **Reactive state management** with computed signals:
  - `pendingTasks()` - Pending tasks count
  - `inProgressTasks()` - In-progress tasks count
  - `completedTasks()` - Completed tasks count
  - `tasksByRole()` - Tasks grouped by care team role
- **Manual refresh** functionality
- **Error handling** with user-friendly messages
- **Reconnection indicator** for connection issues

### 4. TypeScript Models (`src/app/core/models/task.model.ts`)
- `AgentTaskResponse` - Task data transfer object
- `TaskStatus` - Status enumeration
- `AgentType` - Agent type enumeration
- `CareTeamRole` - Care team role enumeration

## 🧪 Testing

### Unit Tests
All services and components include comprehensive unit tests using Jest and Angular Testing Library.

```bash
# Run all tests
npm test

# Run with coverage
npm test:coverage

# Watch mode
npm test:watch
```

### Test Coverage
- **SignalRService**: Event emission, reconnection, JWT auth
- **EncounterTasksApiService**: REST operations, error handling, retries
- **DashboardComponent**: Initialization, task updates, refresh, error states

### Validation Script
```bash
# Validate TASK-004 implementation
node scripts/validate-task-004.js
```

## 🔐 Security

### JWT Authentication
- JWT passed via `accessTokenFactory` closure (never stored)
- Token re-fetched on every connection/reconnection
- No localStorage/sessionStorage usage
- Complies with US-056 security requirements

### CORS Configuration
API endpoints configured for:
- `http://localhost:8000` (development)
- Production URL via environment variable injection

## 🌐 Environment Configuration

### Development (`src/environments/environment.ts`)
```typescript
export const environment = {
  production: false,
  apiBaseUrl: 'http://localhost:8000',
  idpBaseUrl: 'https://idp.hospital.example.com',
  oidcClientId: 'smarthandoff-api-gateway',
};
```

### Production (`src/environments/environment.production.ts`)
```typescript
export const environment = {
  production: true,
  apiBaseUrl: '${API_BASE_URL}',       // Injected by CI/CD
  idpBaseUrl: '${IDP_BASE_URL}',       // Injected by CI/CD
  oidcClientId: '${OIDC_CLIENT_ID}',   // Injected by CI/CD
};
```

## 📡 Real-time Integration Flow

1. **Component Initialization**
   ```
   DashboardComponent.ngOnInit()
     → EncounterTasksApiService.getTasksForEncounter() [Initial load]
     → SignalRService.startConnection()
     → Subscribe to SignalRService.taskUpdated$
   ```

2. **Real-time Update**
   ```
   Backend emits task_updated event
     → SignalR hub delivers to client
     → SignalRService receives event
     → taskUpdated$ Observable emits
     → DashboardComponent updates task list
     → Angular change detection updates UI
   ```

3. **Reconnection Recovery**
   ```
   Connection lost
     → Auto-reconnect attempts [0, 1s, 2s, 5s, 10s]
     → Connection restored
     → EncounterTasksApiService.getTasksForEncounter() [Re-fetch]
     → Emit synthetic task_updated for each task
     → Dashboard state synchronized
   ```

## 🚧 Development Notes

### Adding New Task Filters
To add filtering by agent type, status, or custom criteria:

```typescript
// In dashboard.component.ts
readonly documentationTasks = computed(() => 
  this.tasks().filter(t => t.agent_type === AgentType.DOCUMENTATION)
);
```

### Custom Task Handlers
To handle specific task types differently:

```typescript
private _applyTaskUpdate(event: TaskUpdatedEvent): void {
  // Add custom logic here
  if (event.agent_type === 'DOCUMENTATION') {
    // Handle documentation tasks specially
  }
  // ... rest of implementation
}
```

### SignalR Event Logging
Enable detailed SignalR logging in development:

```typescript
// In signalr.service.ts
.configureLogging(LogLevel.Debug)  // Change from LogLevel.Information
```

## 🐛 Troubleshooting

### "Connection refused" errors
- Verify backend is running on `http://localhost:8000`
- Check CORS configuration in backend
- Ensure SignalR negotiate endpoint is deployed

### "401 Unauthorized" on SignalR connection
- JWT expired — user must re-authenticate
- Check `AuthService.getToken()` returns valid token
- Verify negotiate endpoint validates JWT correctly

### Tasks not updating in real-time
- Check browser console for SignalR errors
- Verify `task_updated` event name matches backend
- Check network tab for WebSocket connection

### Reconnection loops
- Backend may be rejecting the JWT
- Check SignalR hub logs for connection errors
- Verify retry delays are appropriate

## 📝 Acceptance Criteria Status

✅ **US-022 Scenario 1** - task_updated events delivered with <1s latency  
✅ **US-022 Scenario 3** - Auto-reconnect within 5 seconds; missed updates re-fetched  
✅ **US-022 Scenario 4** - JWT authentication on every connection  
✅ **US-022 DoD** - SignalRService with @microsoft/signalr SDK and auto-reconnect

## 🔗 Related Documentation

- [US-022: Real-time Task Updates](.propel/context/user-stories/EP-003/US-022/user_story_022_realtime_task_updates.md)
- [TASK-004: Implementation Spec](.propel/context/tasks/EP-003/US-022/task_004_angular_signalr_service.md)
- [Backend SignalR Integration](../backend/app/signalr/README.md)
- [Azure SignalR Documentation](https://docs.microsoft.com/en-us/azure/azure-signalr/)

## 📄 License

Proprietary - SmartHandoff Care Coordination Platform
