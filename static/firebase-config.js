// Configuration Firebase pour les comptes (favoris, alertes et annonces masquées synchronisés).
// Mettre window.FIREBASE_CONFIG = null pour désactiver les comptes : le site fonctionne alors sans connexion.
// Ces valeurs ne sont pas secrètes : elles identifient le projet, la sécurité vient des règles Firestore
// (firestore.rules) et des domaines autorisés dans Firebase Authentication.
window.FIREBASE_CONFIG = {
  apiKey: "AIzaSyDLNxJPlwaStyW8nJlOXWcTS4YUk63SELE",
  authDomain: "airsoft-occaz-bc0eb.firebaseapp.com",
  projectId: "airsoft-occaz-bc0eb",
  storageBucket: "airsoft-occaz-bc0eb.firebasestorage.app",
  messagingSenderId: "858417217541",
  appId: "1:858417217541:web:0eab3162a486aa76565c6c",
};
