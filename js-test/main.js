const SpotifyWebApi = require('spotify-web-api-node');
const base64url = require('base64url');
const Cookies = require("js-cookie");

var clientId = "d85de6c0c70241d1befe36e2c2d382e3";
var redirectUri = "http://localhost:5000/callback";

var spotifyApi = new SpotifyWebApi();

async function auth() {
    function redirectForAuthorizationCode(code_challenge) {
        var data = {
            "client_id": clientId,
            "response_type": "code",
            "redirect_uri": redirectUri,
            "scope": "user-library-read",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }
        var query = new URLSearchParams(data).toString();
        var auth_uri = "https://accounts.spotify.com/authorize?" + query;
        // redirect
        window.location.replace(auth_uri);
    }

    async function getAccessToken(authorization_code, code_verifier) {
        var token_uri = `https://accounts.spotify.com/api/token`
        var data = {
            "client_id": clientId,
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": redirectUri,
            "code_verifier": code_verifier,
        };

        var method = "POST";
        var headers = new Headers();
        headers.set("Content-Type", 'application/x-www-form-urlencoded');
        var body = new URLSearchParams(data).toString(); 
        console.log(body);

        var promise = fetch(token_uri, {
            method: method, 
            body: body,
            headers: headers,
        }).then(response => {
            console.log("Request complete! response:", response);
            return response.json().then(
                function(response_body) {
                    var access_token = response_body['access_token'];
                    var refresh_token = response_body['refresh_token'];
                    var expires_in = response_body['expires_in'];
                    expires_in = new Date(new Date().getTime() + (parseInt(expires_in) - 10)  * 1000);
                    console.log("expires in: " + expires_in);
                    Cookies.set("access_token", access_token, {expires: expires_in});
                    Cookies.set("refresh_token", refresh_token);
                    return [access_token, refresh_token];
                }
            );
        });
        return promise;
    }

    async function getRefreshedAccessToken(refresh_token) {
        var token_uri = `https://accounts.spotify.com/api/token`
        var data = {
            "client_id": clientId,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        };

        var method = "POST";
        var headers = new Headers();
        headers.set("Content-Type", 'application/x-www-form-urlencoded');
        var body = new URLSearchParams(data).toString(); 
        console.log(body);

        var promise = fetch(token_uri, {
            method: method, 
            body: body,
            headers: headers,
        }).then(response => {
            console.log("Request complete! response:", response);
            return response.json().then(
                function(response_body) {
                    var access_token = response_body['access_token'];
                    var refresh_token = response_body['refresh_token'];
                    var expires_in = response_body['expires_in'];
                    expires_in = new Date(new Date().getTime() + (parseInt(expires_in) - 10)  * 1000);
                    console.log("expires in: " + expires_in);
                    Cookies.set("access_token", access_token, {expires: expires_in});
                    Cookies.set("refresh_token", refresh_token);
                    return [access_token, refresh_token];
                }
            );
        });
        return promise;
    }


    // https://stackoverflow.com/questions/18118824/javascript-to-generate-random-password-with-specific-number-of-letters
    function cryptoRandomString(length) {
        // https://developer.spotify.com/documentation/general/guides/authorization-guide/#authorization-code-flow-with-proof-key-for-code-exchange-pkce
        // It can contain letters, digits, underscores, periods, hyphens, or tildes.
        var charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-~";
        var i;
        var result = "";
        // https://developer.mozilla.org/en-US/docs/Web/API/Window/crypto
        var crypto = window.crypto || window.msCrypto; // for IE 11
        values = new Uint32Array(length);
        crypto.getRandomValues(values);
        for(i = 0; i < length; i++) {
            result += charset[values[i] % charset.length];
        }
        return result;
    }
    
    async function createChallengeVerifierAndCode() {
        var code_verifier = cryptoRandomString(128);
        var code_verifier_bytes = (new TextEncoder()).encode(code_verifier);
        var hash = await window.crypto.subtle.digest("SHA-256", code_verifier_bytes);
        var code_challenge = base64url(hash);
        return [code_verifier, code_challenge];
    }

    // Check url for auth information
    if (urlParams.get("error")) {
        console.log("User denied access");
    } else if (urlParams.get("code")) {
        var authorization_code = urlParams.get("code");
        console.log("Got auth token: " + authorization_code);
        Cookies.set("authorization_code", authorization_code);
    }

    // Check cookies for auth information
    var code_challenge = Cookies.get("code_challenge");
    var code_verifier = Cookies.get("code_verifier");
    var authorization_code = Cookies.get("authorization_code");
    var access_token = Cookies.get("access_token");
    var refresh_token = Cookies.get("refresh_token");

    if (access_token) {
        return Promise(() => {return [access_token, refresh_token]});
    }

    if (authorization_code && code_verifier) {
        // We've generated an auth_code and code_verifier
        // and been redirected to /callback 
        var access_and_refresh_tokens = getAccessToken(authorization_code, code_verifier);
        Cookies.remove("code_challenge");
        Cookies.remove("code_verifier");
        Cookies.remove("authorization_code");
        return access_and_refresh_tokens;
    } else {
        if (refresh_token) {
            // We have a refresh token on hand and need to get a new access and refresh token
            var access_and_refresh_tokens = getRefreshedAccessToken(refresh_token);
            return access_and_refresh_tokens
        } else {
            // We are starting the auth flow and need to generate a code_verifier and code_challange
            // before redirecting to spotify for an auth_code
            var result = await createChallengeVerifierAndCode();
            code_verifier = result[0];
            code_challenge = result[1];
            Cookies.set("code_verifier", code_verifier);
            Cookies.set("code_challenge", code_challenge);
            redirectForAuthorizationCode(code_challenge);    
        }
    }    
}

function logout() {
    Cookies.remove("code_challenge");
    Cookies.remove("code_verifier");
    Cookies.remove("authorization_code");
    Cookies.remove("access_token");
    Cookies.remove("refresh_token");
    window.location.reload();
}

function initApi() {
    var access_token = Cookies.get("access_token");
    var refresh_token = Cookies.get("refresh_token");
    spotifyApi.setAccessToken(access_token);
    spotifyApi.setRefreshToken(refresh_token);
}

// From: https://github.com/thelinmichael/spotify-web-api-node/issues/217
async function callSpotifyWithRetry(func, retries=0, max_retries=10) {
    try {
        return await func();
    } catch (e) {
        if (retries <= max_retries) {
            if (e && e.statusCode === 429) {
                // +1 sec leeway
                const retryAfter = (parseInt(e.headers['retry-after'], 10) + 1) * 1000;
                console.log(`sleeping for: ${retryAfter.toString()}`);
                await new Promise((r) => setTimeout(r, retryAfter));
            }
            return await callSpotifyWithRetry(func, retries + 1, max_retries);
        } else {
            throw e;
        }
    }    
}

async function enumerateTracks(offset, limit) {
    console.log("getting tracks at " + offset);
    var func = () => {
        return spotifyApi.getMySavedTracks({
            "limit": limit,
            "offset": offset
        })
    }
    return callSpotifyWithRetry(func, 0, 10).then(
        function(response) {
            console.log("got tracks at: " + offset + " response: " + response);
            var retDict = {};
            for (var [index, track] of response.body.items.entries()) {
                retDict[index + offset] = track;
            }
            return retDict;
        },
        function(error) {
            console.log("error " + error + " at " + offset);
            return {};
        }
    )
}

function getAllTracks() {
    initApi();

    return spotifyApi.getMySavedTracks().then(
        function (response) {
            console.log("getting all tracks");
            var total = response.body.total;
            var limit = 50;
            var numCalls = parseInt(total / limit) + 1;
            var allData = {};
            var promises = [];
            for (var i = 0; i < numCalls; i++) {
                promises.push(enumerateTracks(i * limit, limit));
            };
            return Promise.all(promises).then(function (allResults) {
                console.log("resolved promises: " + allResults);
                for (var result of allResults) {
                    for (var index in result) {
                        console.log("got data for " + index);
                        allData[index] = result[index];
                    }
                }
                return allData
            }, function(error) {
                console.log("Error resolving promises: " + error);
            });
        }
    )
}

function loadPage() {
    initApi();
    // spotifyApi.getMySavedTracks().then(
    //     function(data) {
    //         var ul = document.createElement("ul");
    //         for (var item of data.body.items) {
    //             var li = document.createElement("li");
    //             li.innerHTML = item.track.name + " by " + item.track.artists[0].name + " from " + item.track.album.name;
    //             ul.appendChild(li)
    //             document.body.appendChild(ul);
    //         }
    //         var limit = document.createElement("p");
    //         limit.innerHTML = "Showing " + 
    //             (parseInt(data.body.offset) + 1).toString() + 
    //             "-" + (parseInt(data.body.offset) + parseInt(data.body.limit) + 1).toString() +
    //             " of " + data.body.total;
    //         document.body.appendChild(limit);
    //     },
    //     function(err) {
    //         console.error(err);
    //     }
    // );
    getAllTracks().then(
        function(allTracks) {
            var ul = document.createElement("ul");
            for (var [index, item] of Object.entries(allTracks)) {
                var li = document.createElement("li");
                console.log(item);
                li.innerHTML = item.track.name + " by " + item.track.artists[0].name + " from " + item.track.album.name;
                ul.appendChild(li)
            }
            document.body.appendChild(ul);
        }
    );
}

var urlQuery = window.location.search;
var urlParams = new URLSearchParams(urlQuery);

// Check cookies for auth information
var code_challenge = Cookies.get("code_challenge");
var code_verifier = Cookies.get("code_verifier");

var access_token = Cookies.get("access_token");
var refresh_token = Cookies.get("refresh_token");

if (access_token || refresh_token) {
    if (window.location.href == redirectUri) {
        window.location.href = "/";
    }
    var login_button = document.getElementById("login-button");
    login_button.innerHTML = "Log Out";
    login_button.onclick = logout;

    if (access_token) {
        console.log("have access token: " + access_token);
        loadPage();
    } else if (refresh_token) {
        console.log("need to refresh with: " + refresh_token);
        auth().then(() => {
            console.log("auth completed");
            loadPage();
        });
    } 
} else {
    if (code_challenge && code_verifier) {
        auth().then(() => {
                console.log("auth completed");
                window.location.href = "/";
            }
        );
    } else {
        console.log("need to complete auth!");
        var login_button = document.getElementById("login-button");
        login_button.innerHTML = "Log In";
        login_button.onclick = auth;
    }
}