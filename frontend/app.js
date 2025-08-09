/**
 * Voice AI Assistant - LiveKit Client
 * Based on official LiveKit documentation and examples
 */

class VoiceCall {
    constructor() {
        this.room = null;
        this.isMuted = false;
        this.remoteParticipants = new Map();
        
        // UI Elements
        this.connectBtn = document.getElementById('connectBtn');
        this.disconnectBtn = document.getElementById('disconnectBtn');
        this.muteBtn = document.getElementById('muteBtn');
        this.statusEl = document.getElementById('status');
        this.statusText = document.getElementById('statusText');
        this.localStatus = document.getElementById('localStatus');
        this.participantsList = document.getElementById('participantsList');
        this.logContainer = document.getElementById('logContainer');
        this.remoteAudio = document.getElementById('remoteAudio');
        
        this.initializeEventListeners();
        this.log('Application initialized', 'info');
    }
    
    initializeEventListeners() {
        this.connectBtn.addEventListener('click', () => this.connect());
        this.disconnectBtn.addEventListener('click', () => this.disconnect());
        this.muteBtn.addEventListener('click', () => this.toggleMute());
        
        // Handle page unload
        window.addEventListener('beforeunload', () => {
            if (this.room) {
                this.room.disconnect();
            }
        });
    }
    
    async connect() {
        try {
            this.updateStatus('connecting', 'Connecting...');
            this.connectBtn.disabled = true;
            
            this.log('Getting access token...', 'info');
            const token = await this.getAccessToken();
            
            this.log('Creating LiveKit room...', 'info');
            this.room = new LiveKit.Room({
                adaptiveStream: true,
                dynacast: true,
            });
            
            // Set up event listeners
            this.setupRoomEvents();
            
            // Get server URL and connect
            const serverUrl = await this.getServerUrl();
            this.log(`Connecting to ${serverUrl}...`, 'info');
            
            await this.room.connect(serverUrl, token);
            this.log('Connected to room successfully!', 'success');
            
            // Enable microphone
            this.log('Enabling microphone...', 'info');
            await this.room.localParticipant.enableCameraAndMicrophone(false, true);
            this.log('Microphone enabled', 'success');
            
            this.updateStatus('connected', 'Connected');
            this.localStatus.textContent = 'Connected (Audio)';
            this.connectBtn.disabled = true;
            this.disconnectBtn.disabled = false;
            this.muteBtn.disabled = false;
            
        } catch (error) {
            this.log(`Connection failed: ${error.message}`, 'error');
            this.updateStatus('disconnected', 'Connection Failed');
            this.connectBtn.disabled = false;
            this.disconnectBtn.disabled = true;
            this.muteBtn.disabled = true;
        }
    }
    
    async disconnect() {
        try {
            this.log('Disconnecting...', 'info');
            
            if (this.room) {
                await this.room.disconnect();
                this.room = null;
            }
            
            this.updateStatus('disconnected', 'Disconnected');
            this.localStatus.textContent = 'Not connected';
            this.connectBtn.disabled = false;
            this.disconnectBtn.disabled = true;
            this.muteBtn.disabled = true;
            this.isMuted = false;
            this.muteBtn.textContent = '🎤 Mute';
            
            // Clear remote participants
            this.remoteParticipants.clear();
            this.updateParticipantsList();
            
            this.log('Disconnected successfully', 'success');
            
        } catch (error) {
            this.log(`Disconnect error: ${error.message}`, 'error');
        }
    }
    
    async toggleMute() {
        if (!this.room || !this.room.localParticipant) return;
        
        try {
            const micTrack = this.room.localParticipant.getTrackPublication(LiveKit.Track.Source.Microphone);
            
            if (micTrack) {
                if (this.isMuted) {
                    await micTrack.track.unmute();
                    this.muteBtn.textContent = '🎤 Mute';
                    this.log('Microphone unmuted', 'info');
                } else {
                    await micTrack.track.mute();
                    this.muteBtn.textContent = '🔇 Unmute';
                    this.log('Microphone muted', 'info');
                }
                this.isMuted = !this.isMuted;
            }
        } catch (error) {
            this.log(`Mute toggle failed: ${error.message}`, 'error');
        }
    }
    
    setupRoomEvents() {
        // Room connection events
        this.room.on(LiveKit.RoomEvent.Connected, () => {
            this.log('Room connected event fired', 'success');
        });
        
        this.room.on(LiveKit.RoomEvent.Disconnected, (reason) => {
            this.log(`Room disconnected: ${reason || 'Unknown reason'}`, 'info');
            this.updateStatus('disconnected', 'Disconnected');
            this.connectBtn.disabled = false;
            this.disconnectBtn.disabled = true;
            this.muteBtn.disabled = true;
        });
        
        this.room.on(LiveKit.RoomEvent.Reconnecting, () => {
            this.log('Reconnecting...', 'info');
            this.updateStatus('connecting', 'Reconnecting...');
        });
        
        this.room.on(LiveKit.RoomEvent.Reconnected, () => {
            this.log('Reconnected successfully', 'success');
            this.updateStatus('connected', 'Connected');
        });
        
        // Participant events
        this.room.on(LiveKit.RoomEvent.ParticipantConnected, (participant) => {
            this.log(`Participant joined: ${participant.identity}`, 'success');
            this.remoteParticipants.set(participant.identity, participant);
            this.updateParticipantsList();
        });
        
        this.room.on(LiveKit.RoomEvent.ParticipantDisconnected, (participant) => {
            this.log(`Participant left: ${participant.identity}`, 'info');
            this.remoteParticipants.delete(participant.identity);
            this.updateParticipantsList();
        });
        
        // Track events
        this.room.on(LiveKit.RoomEvent.TrackSubscribed, (track, publication, participant) => {
            this.log(`Track subscribed: ${track.kind} from ${participant.identity}`, 'info');
            
            if (track.kind === LiveKit.Track.Kind.Audio) {
                this.log('Audio track received - attaching to audio element', 'success');
                const audioElement = track.attach();
                audioElement.style.display = 'none';
                document.body.appendChild(audioElement);
                
                // Also try to use the main audio element
                this.remoteAudio.srcObject = new MediaStream([track.mediaStreamTrack]);
                this.remoteAudio.style.display = 'block';
                this.remoteAudio.play().catch(e => this.log(`Audio play failed: ${e.message}`, 'error'));
            }
        });
        
        this.room.on(LiveKit.RoomEvent.TrackUnsubscribed, (track, publication, participant) => {
            this.log(`Track unsubscribed: ${track.kind} from ${participant.identity}`, 'info');
            
            if (track.kind === LiveKit.Track.Kind.Audio) {
                track.detach();
                this.remoteAudio.style.display = 'none';
            }
        });
        
        // Data events
        this.room.on(LiveKit.RoomEvent.DataReceived, (payload, participant) => {
            try {
                const message = new TextDecoder().decode(payload);
                this.log(`Message from ${participant?.identity || 'unknown'}: ${message}`, 'info');
            } catch (error) {
                this.log(`Binary data received from ${participant?.identity || 'unknown'}`, 'info');
            }
        });
        
        // Connection quality
        this.room.on(LiveKit.RoomEvent.ConnectionQualityChanged, (quality, participant) => {
            if (participant.isLocal) {
                this.log(`Connection quality: ${quality}`, 'info');
            }
        });
    }
    
    async getAccessToken() {
        try {
            const response = await fetch('/token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    room_name: 'debt-collection-room',
                    participant_name: 'web-client-' + Date.now(),
                }),
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            return data.token;
            
        } catch (error) {
            throw new Error(`Failed to get access token: ${error.message}`);
        }
    }
    
    async getServerUrl() {
        try {
            const response = await fetch('/config');
            const config = await response.json();
            return config.livekit_url;
        } catch (error) {
            // Fallback to environment or default
            return 'wss://my-first-6hmu3gwv.livekit.cloud';
        }
    }
    
    updateStatus(status, text) {
        this.statusEl.className = `status ${status}`;
        this.statusText.textContent = text;
    }
    
    updateParticipantsList() {
        // Clear existing remote participants from UI
        const existingRemote = this.participantsList.querySelectorAll('.remote-participant');
        existingRemote.forEach(el => el.remove());
        
        // Add current remote participants
        this.remoteParticipants.forEach((participant, identity) => {
            const participantEl = document.createElement('div');
            participantEl.className = 'participant remote-participant';
            participantEl.innerHTML = `
                <span>${identity}</span>
                <span style="color: #28a745;">Online</span>
            `;
            this.participantsList.appendChild(participantEl);
        });
    }
    
    log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${type}`;
        logEntry.textContent = `[${timestamp}] ${message}`;
        
        this.logContainer.appendChild(logEntry);
        this.logContainer.scrollTop = this.logContainer.scrollHeight;
        
        // Limit log entries
        const logEntries = this.logContainer.children;
        if (logEntries.length > 50) {
            this.logContainer.removeChild(logEntries[0]);
        }
        
        // Also log to console for debugging
        console.log(`[VoiceCall] ${message}`);
    }
}

// Global function for clear logs button
function clearLogs() {
    const logContainer = document.getElementById('logContainer');
    logContainer.innerHTML = '<div class="log-entry log-info">Logs cleared...</div>';
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, checking LiveKit...');
    console.log('window.LiveKit:', typeof window.LiveKit);
    console.log('Available globals:', Object.keys(window).filter(k => k.includes('Live') || k.includes('Kit')));
    
    // Check if LiveKit is loaded (try different global names)
    const LK = window.LiveKit || window.LivekitClient || window.livekit;
    if (!LK) {
        console.error('LiveKit SDK not loaded');
        document.getElementById('logContainer').innerHTML = 
            '<div class="log-entry log-error">LiveKit SDK failed to load. DEBUG: Check browser console for details.</div>';
        return;
    }
    
    console.log('LiveKit SDK loaded successfully as:', LK);
    // Make LiveKit available globally for our app
    window.LiveKit = LK;
    window.voiceCall = new VoiceCall();
});