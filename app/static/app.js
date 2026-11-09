function taskPulseApp() {
  return {
    currentUser: null,
    token: localStorage.getItem('taskpulse_token') || null,
    tasks: [],
    members: [],
    notifications: [],
    unreadCount: 0,
    metrics: { total: 0, todo: 0, seen: 0, in_progress: 0, pending_review: 0, completed: 0 },

    // Modals & form state
    authModal: false,
    authMode: 'login',
    authForm: { email: '', password: '', full_name: '', role: 'MEMBER' },

    createModal: false,
    newTask: { title: '', description: '', priority: 'MEDIUM', assignee_id: '', due_date: '' },

    detailModal: false,
    activeTask: null,
    commentText: '',
    commentAttachment: '',

    // Filters
    filterStatus: '',
    filterPriority: '',

    toast: { show: false, message: '' },
    pollInterval: null,

    async initApp() {
      if (this.token) {
        await this.fetchCurrentUser();
        if (this.currentUser) {
          await this.loadAllDashboardData();
          this.startNotificationPolling();
        }
      }
      this.$nextTick(() => lucide.createIcons());
    },

    showToast(message) {
      this.toast.message = message;
      this.toast.show = true;
      setTimeout(() => { this.toast.show = false; }, 3500);
      this.$nextTick(() => lucide.createIcons());
    },

    getHeaders() {
      return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.token}`
      };
    },

    async fetchCurrentUser() {
      try {
        const res = await fetch('/api/v1/auth/me', { headers: this.getHeaders() });
        if (res.ok) {
          this.currentUser = await res.json();
        } else {
          this.logout();
        }
      } catch (err) {
        console.error('Failed to get current user:', err);
        this.logout();
      }
    },

    async loadAllDashboardData() {
      await Promise.all([
        this.fetchTasks(),
        this.fetchMetrics(),
        this.fetchNotifications(),
        this.fetchMembers()
      ]);
      this.$nextTick(() => lucide.createIcons());
    },

    startNotificationPolling() {
      if (this.pollInterval) clearInterval(this.pollInterval);
      // Poll notifications and metrics every 15 seconds
      this.pollInterval = setInterval(async () => {
        if (this.currentUser) {
          await this.fetchNotifications();
          await this.fetchMetrics();
        }
      }, 15000);
    },

    async fetchTasks() {
      try {
        let url = '/api/v1/tasks/?';
        if (this.filterStatus) url += `status=${this.filterStatus}&`;
        if (this.filterPriority) url += `priority=${this.filterPriority}&`;

        const res = await fetch(url, { headers: this.getHeaders() });
        if (res.ok) {
          this.tasks = await res.json();
        }
      } catch (err) {
        console.error('Error fetching tasks:', err);
      } finally {
        this.$nextTick(() => lucide.createIcons());
      }
    },

    async fetchMetrics() {
      try {
        const res = await fetch('/api/v1/tasks/metrics', { headers: this.getHeaders() });
        if (res.ok) {
          this.metrics = await res.json();
        }
      } catch (err) {
        console.error('Error fetching metrics:', err);
      }
    },

    async fetchNotifications() {
      try {
        const res = await fetch('/api/v1/notifications/', { headers: this.getHeaders() });
        if (res.ok) {
          const data = await res.json();
          this.notifications = data.items;
          this.unreadCount = data.unread_count;
        }
      } catch (err) {
        console.error('Error fetching notifications:', err);
      }
    },

    async fetchMembers() {
      if (this.currentUser?.role === 'LEADER') {
        try {
          const res = await fetch('/api/v1/users/members', { headers: this.getHeaders() });
          if (res.ok) {
            this.members = await res.json();
          }
        } catch (err) {
          console.error('Error fetching members:', err);
        }
      }
    },

    async openCreateTaskModal() {
      await this.fetchMembers();
      this.createModal = true;
      this.$nextTick(() => lucide.createIcons());
    },

    async submitCreateTask() {
      try {
        const payload = {
          title: this.newTask.title,
          description: this.newTask.description || null,
          priority: this.newTask.priority,
          assignee_id: this.newTask.assignee_id || null,
          due_date: this.newTask.due_date ? new Date(this.newTask.due_date).toISOString() : null
        };
        const res = await fetch('/api/v1/tasks/', {
          method: 'POST',
          headers: this.getHeaders(),
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          this.showToast('Task successfully created and delegated!');
          this.createModal = false;
          this.newTask = { title: '', description: '', priority: 'MEDIUM', assignee_id: '', due_date: '' };
          await this.loadAllDashboardData();
        } else {
          const err = await res.json();
          alert(err.detail || 'Failed to create task');
        }
      } catch (err) {
        alert('Network error while creating task');
      }
    },

    async openTaskDetail(taskId) {
      try {
        // Fetching task triggers auto "SEEN" status and timestamp update for members
        const res = await fetch(`/api/v1/tasks/${taskId}`, { headers: this.getHeaders() });
        if (res.ok) {
          this.activeTask = await res.json();
          this.detailModal = true;
          await this.fetchTasks();
          await this.fetchMetrics();
        } else {
          alert('Could not retrieve task detail');
        }
      } catch (err) {
        console.error('Error opening task detail:', err);
      } finally {
        this.$nextTick(() => lucide.createIcons());
      }
    },

    async updateTaskStatus(taskId, newStatus, note = '') {
      try {
        const res = await fetch(`/api/v1/tasks/${taskId}/status`, {
          method: 'PATCH',
          headers: this.getHeaders(),
          body: JSON.stringify({ status: newStatus, note: note })
        });
        if (res.ok) {
          this.showToast(`Task transitioned to ${newStatus.replace('_', ' ')}`);
          this.activeTask = await res.json();
          await this.fetchTasks();
          await this.fetchMetrics();
          await this.fetchNotifications();
        } else {
          const err = await res.json();
          alert(err.detail || 'Status transition failed');
        }
      } catch (err) {
        console.error('Error updating status:', err);
      } finally {
        this.$nextTick(() => lucide.createIcons());
      }
    },

    async quickUpdateStatus(task, newStatus) {
      const note = newStatus === 'PENDING_REVIEW' 
        ? (prompt('Deliverables link or note for Leader review:') || 'Ready for review')
        : 'Approved sign-off';
      await this.updateTaskStatus(task.id, newStatus, note);
    },

    async submitTaskComment() {
      if (!this.commentText || !this.activeTask) return;
      try {
        const res = await fetch(`/api/v1/tasks/${this.activeTask.id}/updates`, {
          method: 'POST',
          headers: this.getHeaders(),
          body: JSON.stringify({
            message: this.commentText,
            attachment_url: this.commentAttachment || null
          })
        });
        if (res.ok) {
          const update = await res.json();
          if (!this.activeTask.updates) this.activeTask.updates = [];
          this.activeTask.updates.push(update);
          this.commentText = '';
          this.commentAttachment = '';
          this.showToast('Progress note logged to audit trail');
        }
      } catch (err) {
        alert('Failed to post comment');
      } finally {
        this.$nextTick(() => lucide.createIcons());
      }
    },

    async markNotificationRead(notifId) {
      try {
        await fetch(`/api/v1/notifications/${notifId}/read`, {
          method: 'PATCH',
          headers: this.getHeaders()
        });
        await this.fetchNotifications();
      } catch (err) {
        console.error(err);
      }
    },

    async markAllNotificationsRead() {
      try {
        await fetch('/api/v1/notifications/read-all', {
          method: 'POST',
          headers: this.getHeaders()
        });
        await this.fetchNotifications();
      } catch (err) {
        console.error(err);
      }
    },

    async submitAuth() {
      if (this.authMode === 'login') {
        await this.performLogin(this.authForm.email, this.authForm.password);
      } else {
        try {
          const res = await fetch('/api/v1/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(this.authForm)
          });
          if (res.ok) {
            this.showToast('Account registered! Signing in...');
            await this.performLogin(this.authForm.email, this.authForm.password);
          } else {
            const err = await res.json();
            alert(err.detail || 'Registration failed');
          }
        } catch (err) {
          alert('Network error during registration');
        }
      }
    },

    async performLogin(email, password) {
      try {
        const res = await fetch('/api/v1/auth/login/json', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        });
        if (res.ok) {
          const data = await res.json();
          this.token = data.access_token;
          this.currentUser = data.user;
          localStorage.setItem('taskpulse_token', this.token);
          this.authModal = false;
          this.showToast(`Welcome back, ${this.currentUser.full_name}!`);
          await this.loadAllDashboardData();
          this.startNotificationPolling();
        } else {
          const err = await res.json();
          alert(err.detail || 'Login failed. Please check credentials.');
        }
      } catch (err) {
        alert('Network error during login');
      } finally {
        this.$nextTick(() => lucide.createIcons());
      }
    },

    async quickLogin(email, password, role) {
      // Try to login; if user doesn't exist, register them automatically for seamless demo experience!
      let res = await fetch('/api/v1/auth/login/json', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });

      if (!res.ok) {
        // Auto register demo user
        const regRes = await fetch('/api/v1/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: email,
            password: password,
            full_name: role === 'LEADER' ? 'Sarah Connor (Team Lead)' : 'John Connor (Engineer)',
            role: role
          })
        });
        if (regRes.ok) {
          await this.performLogin(email, password);
          return;
        }
      }

      await this.performLogin(email, password);
    },

    logout() {
      this.token = null;
      this.currentUser = null;
      this.tasks = [];
      this.notifications = [];
      this.unreadCount = 0;
      localStorage.removeItem('taskpulse_token');
      if (this.pollInterval) clearInterval(this.pollInterval);
      this.$nextTick(() => lucide.createIcons());
    },

    getPriorityClass(priority) {
      switch (priority) {
        case 'CRITICAL': return 'bg-rose-500/10 text-rose-400 border border-rose-500/20';
        case 'HIGH': return 'bg-amber-500/10 text-amber-400 border border-amber-500/20';
        case 'MEDIUM': return 'bg-sky-500/10 text-sky-400 border border-sky-500/20';
        case 'LOW': return 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
        default: return 'bg-slate-800 text-slate-300';
      }
    },

    getStatusClass(status) {
      switch (status) {
        case 'TODO': return 'bg-slate-800 text-slate-300';
        case 'SEEN': return 'bg-sky-900/40 text-sky-300 border border-sky-600/30';
        case 'IN_PROGRESS': return 'bg-indigo-900/40 text-indigo-300 border border-indigo-600/30';
        case 'PENDING_REVIEW': return 'bg-amber-900/40 text-amber-300 border border-amber-600/30';
        case 'COMPLETED': return 'bg-emerald-900/40 text-emerald-300 border border-emerald-600/30';
        default: return 'bg-slate-800 text-slate-300';
      }
    },

    isOverdue(dueDate) {
      if (!dueDate) return false;
      return new Date(dueDate) < new Date();
    },

    formatDate(dateStr) {
      if (!dateStr) return '';
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    }
  };
}
