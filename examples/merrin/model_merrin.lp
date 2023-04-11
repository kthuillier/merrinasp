#program base.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% PRÉ-CALCUL SUR LES OBSERVATIONS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

time(T1) :- next(T1, _).
time(T2) :- next(_, T2).

experiment(E) :- time((E, _)).

nb_obs(E, S) :- S = #count {T: time((E, T)) }, experiment(E).
1 { totalTimes(E, S..S+K) } 1 :- experiment(E), nb_obs(E, S), maxObsToAdd(K).

:- tlink(_, (E, TM)), totalTimes(E, S), S < TM.

ttime((E, TM)) :- totalTimes(E, S), TM = (1..S). 
tnext((E, TM1), (E, TM2)) :- ttime((E, TM1)), ttime((E, TM2)), TM1 + 1 = TM2.

:- next((E, TO1), (E, TO2)), tlink((E, TO1), (E, TM1)), tlink((E, TO2), (E, TM2)), TM2 <= TM1.
:- next((E, TO1), (E, TO2)), tlink((E, TO1), (E, TM1)), tlink((E, TO2), (E, TM2)), maxObsToAdd(K), K + 1 < TM2 - TM1.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% PRÉPARATION DES DONNÉES
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

inp(X,R) :- reactant(X,R,_), not product(X,_,_).
out(X,R) :- product(X,R,_), not reactant(X,_,_).
r(r,A,R) :- reactant(A,R,_), product(A,_,_).
r(p,A,R) :- product(A,R,_), reactant(A,_,_).

varm(A) :- r(_,A,_).
varm(A) :- r(_,_,A).
varm(A) :- inp(A,_).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% BONESIS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

{clause(N,1..C,L,S): in(L,N,S), maxC(N,C), node(N), node(L)}.

:- clause(N,_,L,S), clause(N,_,L,-S).

1 {constant(N,(-1;1))} 1 :- node(N), not clause(N,_,_,_).

constant(N) :- constant(N,_).

size(N,C,X) :- X = #count {L,S: clause(N,C,L,S)}; clause(N,C,_,_).

:- clause(N,C,_,_); not clause(N,C-1,_,_); C > 1.

:- size(N,C1,X1); size(N,C2,X2); X1 < X2; C1 > C2.

:- size(N,C1,X); size(N,C2,X); C1 > C2; 
    mindiff(N,C1,C2,L1) ; mindiff(N,C2,C1,L2) ; L1 < L2.

clausediff(N,C1,C2,L) :- 
    clause(N,C1,L,_);not clause(N,C2,L,_);clause(N,C2,_,_), C1 != C2.

mindiff(N,C1,C2,L) :- clausediff(N,C1,C2,L); 
    L <= L' : clausediff(N,C1,C2,L'), clause(N,C1,L',_), C1!=C2.

:- size(N,C1,X1); size(N,C2,X2); C1 != C2; X1 <= X2; 
    clause(N,C2,L,S) : clause(N,C1,L,S).

nbnode(NB) :- NB = #count{N: node(N)}.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% DÉFINITION DU MSS RESPECTANT LES OBSERVATIONS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% ÉTAT MÉTABOLIQUE
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% Définition des noeuds.
1 { v(T,A,(1;-1)) } 1 :- ttime(T), varm(A).

% Les noeuds doivent suivre les observations.
:- tlink(TO, TM), obs(TO,A,V), v(TM,A,-V).

% Un métabolite est produit/consommé par au moins une réaction.
:- ttime(T), r(S,A,_), v(T,A,1), v(T,R,-1): r(S,A,R).

% Une réactive active ses réactants et ses produits.
:- ttime(T), r(_,A,R), v(T,R,1), v(T,A,-1).

% Une réaction d'import doit avoir ses réactants dans l'environnement.
:- ttime(T), inp(X,R), v(T,X,-1), v(T,R,1).

1 { v(T,A,(1;-1)) } 1 :- varx(A), ttime(T).

% forward non-emss variables
:- varx(A), w(T,A,V), v(T,A,-V).

% if regulated is 0, mss cannot activate it
:- w(T,A,-1), v(T,A,1), node(A).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% RÉSEAU BOOLÉEN
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%% tune BoNesis encoding for using non-defined nodes
{clause(N,1..C,L,S): in(L,N,S), maxC(N,C), node(N)}.

read(T,A,V) :- tnext(T,_), not inp(A,_), v(T,A,V).
read(T,A,V) :- tnext(T,T2), inp(A,_), tlink(TO2, T2), obs(TO2,A,V).

%% eval
eval(T,A,C,-1)  :- update(T,A), clause(A,C,L,V), read(T,L,-V).
eval(T,A,C,1)   :- read(T,L,V): clause(A,C,L,V); update(T,A), clause(A,C,_,_).
eval(T,A,1)     :- eval(T,A,C,1), clause(A,C,_,_).
eval(T,A,-1)    :- eval(T,A,C,-1): clause(A,C,_,_); update(T,A), clause(A,C,_,_).
eval(T,A,V)     :- update(T,A), constant(A,V).

%% intermediate regulated state
mode(T1,reg) :- tnext(T1,_).

% copy inputs
w(T2,A,V) :- inp(A,_), tnext(_,T2), tlink(TO2, T2), obs(TO2,A,V).
% copy non-updated
w(T2,A,V) :- tnext(T1,T2), not inp(A,_), not update(T1,A), v(T1,A,V).
% apply update
w(T2,A,V) :- tnext(T1,T2), update(T1,A), eval(T1,A,V).

%% variables not in emss
varx(A) :- node(A), not varm(A).

% TODO: 
%   coder la vraie règle (peut passer à 0 seulement si un flux le consomme)?
%   ou autoriser tout changement (revenir au concept de 'control' nodes 
%   dont on ne cherche pas à justifier la valeur)
constant(A,-1) :- inp(A,_).

% no constant
:- constant(A), not inp(A,_).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% DÉBOGAGE
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% Propre a nos donnees issues de FlexFlux (a (X, 0) aucun flux n'est calcule)
v(TM1,R,-1) :- r(_,_,R), next(TO1,_), TO1=(_,0), tlink(TO1,TM1).

% For monotonic constraints
w(T,A,1) :- tnext(_, T), not node(A), r(_,_,A).
w_obs(TO, A, 1) :- next(_, TO), not node(A), r(_, _, A).
w_obs(TO, A, V) :- tlink(TO, TM), w(TM, A, V).
:- tlink(TO, TM), node(A), w_obs(TO, A, V), w(TM, A, -V).

update(T1,A) :- mode(T1,reg), node(A), not inp(A,_).

#minimize { V, E : totalTimes(E, V) }.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% INPUTS/OUTPUTS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
:- tnext(T1, T2), inp(X, R), v(T1, X, 1), v(T2, X,-1), v(T1, R,-1).
:- tnext(T1, T2), out(X, R), v(T1, X,-1), v(T2, X, 1), v(T1, R,-1).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% SHOW
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

maxObsToAdd(0).
coeff("0.05").
epsilon("0.0001").

debug(T) :- next(_, T), T=(_, _).

#show.
#show clause/4.