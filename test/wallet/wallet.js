const scanButton = document.getElementById('scan-button');
const walletGrid = document.getElementById('wallet-grid');
const readerDiv = document.getElementById('reader');
const questionScreen = document.getElementById('question-screen');
const shareQuestion = document.getElementById('share-question');
const yesButton = document.getElementById('yes-button');
const noButton = document.getElementById('no-button');

let credentials = [];

function loadCredentials() {
  const storedCredentials = localStorage.getItem('credentials');
  if (storedCredentials) {
    credentials = JSON.parse(storedCredentials);
  }
}

function saveCredentials() {
  localStorage.setItem('credentials', JSON.stringify(credentials));
}

function displayCredentials() {
  walletGrid.innerHTML = '';
  credentials.forEach((cred) => {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `<h3>${cred.name}</h3><p>Valid until ${cred.validUntil}</p>`;
    walletGrid.appendChild(card);
  });
}

scanButton.addEventListener('click', () => {
  readerDiv.style.display = 'block';
  const html5QrCode = new Html5Qrcode("reader");

  html5QrCode.start(
    { facingMode: "environment" },
    { fps: 10, qrbox: 250 },
    (decodedText) => {
      try {
        const data = JSON.parse(decodedText);

        // If the QR-code is from a verifier, ask to share specific card
        if (data.verifier) {
          const requestedCard = data.requestedCard;
          const requester = data.requester;

          // Toon vraag in het scherm
          readerDiv.style.display = 'none';
          questionScreen.style.display = 'block';
          shareQuestion.innerText = `Wil je het kaartje "${requestedCard}" delen met ${requester}?`;

          // Handle Yes/No response
          yesButton.onclick = () => {
            // Sla de deelactie op in localStorage
            const timestamp = new Date().toLocaleString();
            credentials.push({
              name: `Kaartje "${requestedCard}" gedeeld met ${requester}`,
              validUntil: timestamp
            });
            saveCredentials();
            displayCredentials();
            questionScreen.style.display = 'none'; // Ga terug naar het hoofscherm
          };

          noButton.onclick = () => {
            questionScreen.style.display = 'none'; // Ga terug naar het hoofscherm
          };

        } else {
          // Verwerk issuer-QR-code
          credentials.push({ name: data.name || "Unknown", validUntil: 'N/A', data: data });
          saveCredentials();
          displayCredentials();
        }

        html5QrCode.stop().then(() => {
          readerDiv.style.display = 'none';
        });

      } catch (error) {
        console.error(`QR-code parse error: ${error}`);
      }
    },
    (errorMessage) => {
      console.error(`QR scan failed: ${errorMessage}`);
    }
  );
});

loadCredentials();
displayCredentials();
