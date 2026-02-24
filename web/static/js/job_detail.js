function jobDetail(jobId, statusUrl, initialStatus, initialProgress, initialError) {
  return {
    status: initialStatus || 'queued',
    progress: initialProgress || 'Queued',
    startedAt: '—',
    finishedAt: '—',
    errorMessage: initialError || '',
    summary: {
      health_score: null,
      high_priority: null,
      medium_priority: null,
      low_priority: null,
      videos_analyzed: null,
    },
    pollHandle: null,

    start() {
      this.fetchStatus();
      this.pollHandle = setInterval(() => this.fetchStatus(), 5000);
    },

    stopPollingIfTerminal() {
      if (['completed', 'failed'].includes(this.status) && this.pollHandle) {
        clearInterval(this.pollHandle);
        this.pollHandle = null;
      }
    },

    async fetchStatus() {
      try {
        const response = await fetch(statusUrl, { credentials: 'same-origin' });
        if (!response.ok) {
          return;
        }
        const data = await response.json();
        this.status = data.status;
        this.progress = data.progress_step || '—';
        this.errorMessage = data.error_message || '';
        this.summary = data.summary || this.summary;

        this.startedAt = data.started_at ? new Date(data.started_at).toLocaleString() : '—';
        this.finishedAt = data.finished_at ? new Date(data.finished_at).toLocaleString() : '—';

        this.stopPollingIfTerminal();
      } catch (error) {
        console.error('Status fetch failed', error);
      }
    },

    async downloadArtifact(type) {
      const endpoint = `/api/audits/${jobId}/artifacts/${type}`;
      try {
        const response = await fetch(endpoint, { credentials: 'same-origin' });
        if (!response.ok) {
          alert('Artifact not available yet.');
          return;
        }
        const data = await response.json();
        if (!data.url) {
          alert('Artifact URL missing.');
          return;
        }
        window.open(data.url, '_blank');
      } catch (error) {
        alert('Could not fetch artifact link.');
      }
    },
  };
}
