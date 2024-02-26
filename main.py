from flask import Flask, request, jsonify
from flask_cors import CORS

import firebase_admin
from firebase_admin import firestore, credentials
from firebase_admin.firestore import ArrayUnion, ArrayRemove
import datetime
from flask_socketio import SocketIO

# Application Default credentials are automatically created.
cred = credentials.Certificate("./creds.json")
firebaseApp = firebase_admin.initialize_app(credential=cred)
db = firestore.client()

app = Flask(__name__)
app.secret_key = "36o89bn79o6b78q34tv5"
socketio = SocketIO(app, cors_allowed_origins="*")

CORS(app, resources={r"*": {"origins": "*"}})

connList = {}


def getCurrentTimeStamp():
    return datetime.datetime.now()


def setUserStatus(username, status):
    db.collection("status").document("status_doc").update({username: status})


@socketio.on("connect")
def handleConnection():
    print("Connected", request.sid)


@socketio.on("disconnect")
def handleDisconnection():
    print("Disconnected", request.sid)
    if request.sid in connList:
        setUserStatus(connList[request.sid], "offline")
        del connList[request.sid]
        print(connList)


@socketio.on("uid")
def handleUid(username):
    connList[request.sid] = username
    print(connList)
    setUserStatus(username, "online")


@app.route("/createUser", methods=["POST"])
def createUser():
    data = request.json
    uid = data["uid"]
    userData = {
        "uid": uid,
        "friends": [],
        "friendRequests": [],
        "visibility": "offline",
        "username": data["username"],
        "email": data["email"],
    }
    doc_ref = db.collection("users").document(uid)
    doc_ref.set(userData)

    return jsonify({"message": "User Created Successfully"}), 200


@app.route("/addFriend", methods=["POST"])
def addFriend():
    data = request.json
    uid = data["uid"]
    frusername = data["frusername"]

    self_doc_ref = db.collection("users").document(uid)
    friend_docs_ref = db.collection("users").where("username", "==", frusername)

    self_doc = self_doc_ref.get().to_dict()
    try:
        friend_doc = friend_docs_ref.get()[0].to_dict()
        friend_doc_ref = db.collection("users").document(friend_doc["uid"])
    except IndexError:
        return jsonify({"error": "User not found"}), 200

    print(self_doc)

    curTime = getCurrentTimeStamp()

    frData = {
        "timestamp": curTime,
        "type": "incoming",
        "username": self_doc["username"],
    }

    selfData = {
        "timestamp": curTime,
        "type": "outgoing",
        "username": friend_doc["username"],
    }

    print(frData, selfData)

    self_doc_ref.update({"friendRequests": ArrayUnion([selfData])})
    friend_doc_ref.update({"friendRequests": ArrayUnion([frData])})

    return jsonify({"message": "Friend Request Sent"}), 200


@app.route("/acceptFriend", methods=["POST"])
def acceptFriend():
    data = request.json

    uid = data["uid"]
    frusername = data["frusername"]

    fruid = (
        db.collection("users")
        .where("username", "==", frusername)
        .get()[0]
        .to_dict()["uid"]
    )

    self_doc_ref = db.collection("users").document(uid)
    friend_doc_ref = db.collection("users").document(fruid)

    self_doc = self_doc_ref.get().to_dict()
    friend_doc = friend_doc_ref.get().to_dict()

    chat_ref = db.collection("chats").add({"messages": []})[1]
    chatId = chat_ref.id

    acceptTime = getCurrentTimeStamp()

    selfData = {
        "username": friend_doc["username"],
        "timestamp": acceptTime,
        "chatId": chatId,
    }

    friendData = {
        "username": self_doc["username"],
        "timestamp": acceptTime,
        "chatId": chatId,
    }

    self_username = self_doc["username"]
    for i in friend_doc["friendRequests"]:
        if i["username"] == self_username:
            reqObj = i
            break
    friend_username = friend_doc["username"]
    for i in self_doc["friendRequests"]:
        if i["username"] == friend_username:
            otherReqObj = i
            break

    self_doc_ref.update({"friends": ArrayUnion([selfData])})
    friend_doc_ref.update({"friends": ArrayUnion([friendData])})

    print(reqObj, otherReqObj)

    self_doc_ref.update({"friendRequests": ArrayRemove([otherReqObj])})
    friend_doc_ref.update({"friendRequests": ArrayRemove([reqObj])})

    return jsonify({"message": "Friend Added"}), 200


@app.route("/rejectFriend", methods=["POST"])
def rejectFriend():
    data = request.json
    uid = data["uid"]
    frusername = data["frusername"]

    fruid = (
        db.collection("users")
        .where("username", "==", frusername)
        .get()[0]
        .to_dict()["uid"]
    )

    self_doc_ref = db.collection("users").document(uid)
    friend_doc_ref = db.collection("users").document(fruid)

    self_doc = self_doc_ref.get().to_dict()
    friend_doc = friend_doc_ref.get().to_dict()

    self_username = self_doc["username"]
    for i in friend_doc["friendRequests"]:
        if i["username"] == self_username:
            reqObj = i
            break
    friend_username = friend_doc["username"]
    for i in self_doc["friendRequests"]:
        if i["username"] == friend_username:
            otherReqObj = i
            break

    self_doc_ref.update({"friendRequests": ArrayRemove([otherReqObj])})
    friend_doc_ref.update({"friendRequests": ArrayRemove([reqObj])})

    return jsonify({"message": "Friend Request Rejected"}), 200


@app.route("/setVisibility", methods=["POST"])
def setOnline():
    print(request.json)
    data = request.json
    username = data["username"]
    value = data["value"]

    db.collection("status").document("status_doc").update({username: value})
    return jsonify({"message": "Visibility set"}), 200


if __name__ == "__main__":
    # app.run(debug=True, host="0.0.0.0", port=5000)
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
