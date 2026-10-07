"""Catálogo automático inicial do Aprender."""
from dataclasses import dataclass

@dataclass(frozen=True)
class SeedWord:
    word: str
    part_of_speech: str
    translation: str
    example_sentence: str
    example_sentences: tuple[str, str, str]
    distractors: tuple[str, str, str]
    level: str

AUTO_VOCAB = {
    "ingles": [
        SeedWord("money","noun","dinheiro","I need some money.",("I need some money.","She saved money for a trip.","Do you have enough money?"),("comida","trabalho","problema"),"A1"),
        SeedWord("food","noun","comida","The food is good.",("The food is good.","We ordered some food.","I love Italian food."),("dinheiro","amigo","trabalho"),"A1"),
        SeedWord("friend","noun","amigo","My friend lives here.",("My friend lives here.","I met an old friend yesterday.","My best friend loves music."),("problema","comida","dinheiro"),"A1"),
        SeedWord("work","noun","trabalho","I have a lot of work today.",("I have a lot of work today.","She is looking for work.","He starts work at eight."),("comida","amigo","problema"),"A1"),
        SeedWord("problem","noun","problema","We have a small problem.",("We have a small problem.","There is a problem with the car.","Let me help you solve this problem."),("trabalho","dinheiro","amigo"),"A2"),
        SeedWord("want","verb","querer","I want some water.",("I want some water.","I want to go home.","What do you want for dinner?"),("precisar","gostar","saber"),"A1"),
        SeedWord("need","verb","precisar","I need more time.",("I need more time.","We need to talk.","Do you need any help?"),("querer","gostar","ter"),"A1"),
        SeedWord("like","verb","gostar","I like this song.",("I like this song.","I like coffee in the morning.","Do you like this movie?"),("querer","precisar","saber"),"A1"),
        SeedWord("of course","expression","claro","Of course, I can help you.",("Of course, I can help you.","Of course I remember you.","Of course, you can come with us."),("talvez","desculpa","obrigado"),"A1"),
        SeedWord("I don't know","expression","eu não sei","I don't know the answer.",("I don't know the answer.","I don't know what happened.","Sorry, I don't know."),("eu entendo","até logo","com licença"),"A1"),
    ],
    "italiano": [
        SeedWord("soldi","noun","dinheiro","Ho bisogno di soldi.",("Ho bisogno di soldi.","Ha risparmiato soldi per il viaggio.","Hai abbastanza soldi?"),("comida","trabalho","problema"),"A1"),
        SeedWord("cibo","noun","comida","Il cibo è buono.",("Il cibo è buono.","Abbiamo ordinato del cibo.","Mi piace il cibo italiano."),("dinheiro","amigo","trabalho"),"A1"),
        SeedWord("amico","noun","amigo","Il mio amico vive qui.",("Il mio amico vive qui.","Ho incontrato un vecchio amico ieri.","Il mio migliore amico ama la musica."),("problema","comida","dinheiro"),"A1"),
        SeedWord("lavoro","noun","trabalho","Ho molto lavoro oggi.",("Ho molto lavoro oggi.","Sta cercando lavoro.","Inizia a lavorare alle otto."),("comida","amigo","problema"),"A1"),
        SeedWord("problema","noun","problema","Abbiamo un piccolo problema.",("Abbiamo un piccolo problema.","C'è un problema con la macchina.","Ti aiuto a risolvere questo problema."),("trabalho","dinheiro","amigo"),"A2"),
        SeedWord("volere","verb","querer","Voglio un po' d'acqua.",("Voglio un po' d'acqua.","Voglio andare a casa.","Cosa vuoi per cena?"),("precisar","gostar","saber"),"A1"),
        SeedWord("avere bisogno","verb","precisar","Ho bisogno di più tempo.",("Ho bisogno di più tempo.","Dobbiamo parlare.","Hai bisogno di aiuto?"),("querer","gostar","ter"),"A1"),
        SeedWord("piacere","verb","gostar","Mi piace questa canzone.",("Mi piace questa canzone.","Mi piace il caffè al mattino.","Ti piace questo film?"),("querer","precisar","saber"),"A1"),
        SeedWord("certo","expression","claro","Certo, posso aiutarti.",("Certo, posso aiutarti.","Certo che mi ricordo di te.","Certo, puoi venire con noi."),("talvez","desculpa","obrigado"),"A1"),
        SeedWord("non lo so","expression","eu não sei","Non lo so.",("Non lo so.","Non so cosa è successo.","Scusa, non lo so."),("eu entendo","até logo","com licença"),"A1"),
    ],
    "frances": [
        SeedWord("argent","noun","dinheiro","J'ai besoin d'argent.",("J'ai besoin d'argent.","Elle a économisé de l'argent pour le voyage.","Tu as assez d'argent ?"),("comida","trabalho","problema"),"A1"),
        SeedWord("nourriture","noun","comida","La nourriture est bonne.",("La nourriture est bonne.","Nous avons commandé de la nourriture.","J'aime la nourriture italienne."),("dinheiro","amigo","trabalho"),"A1"),
        SeedWord("ami","noun","amigo","Mon ami habite ici.",("Mon ami habite ici.","J'ai rencontré un vieil ami hier.","Mon meilleur ami aime la musique."),("problema","comida","dinheiro"),"A1"),
        SeedWord("travail","noun","trabalho","J'ai beaucoup de travail aujourd'hui.",("J'ai beaucoup de travail aujourd'hui.","Elle cherche du travail.","Il commence le travail à huit heures."),("comida","amigo","problema"),"A1"),
        SeedWord("problème","noun","problema","Nous avons un petit problème.",("Nous avons un petit problème.","Il y a un problème avec la voiture.","Je peux vous aider à résoudre ce problème."),("trabalho","dinheiro","amigo"),"A2"),
        SeedWord("vouloir","verb","querer","Je veux de l'eau.",("Je veux de l'eau.","Je veux rentrer chez moi.","Qu'est-ce que tu veux pour le dîner ?"),("precisar","gostar","saber"),"A1"),
        SeedWord("avoir besoin","verb","precisar","J'ai besoin de plus de temps.",("J'ai besoin de plus de temps.","Nous devons parler.","Tu as besoin d'aide ?"),("querer","gostar","ter"),"A1"),
        SeedWord("aimer","verb","gostar","J'aime cette chanson.",("J'aime cette chanson.","J'aime le café le matin.","Tu aimes ce film ?"),("querer","precisar","saber"),"A1"),
        SeedWord("bien sûr","expression","claro","Bien sûr, je peux vous aider.",("Bien sûr, je peux vous aider.","Bien sûr, je me souviens de vous.","Bien sûr, vous pouvez venir avec nous."),("talvez","desculpa","obrigado"),"A1"),
        SeedWord("je ne sais pas","expression","eu não sei","Je ne sais pas.",("Je ne sais pas.","Je ne sais pas ce qui s'est passé.","Désolé, je ne sais pas."),("eu entendo","até logo","com licença"),"A1"),
    ],
}
