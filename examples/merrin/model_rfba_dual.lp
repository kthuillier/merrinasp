%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% LP
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

reaction(R) :- r(_,_,R).
metabolite(M) :- r(_,M,_).

s(R,M,S) :- product(M,R,S), not out(M,R).
s(R,M,S) :- reactant(M,R,S), not inp(M,R).
s(R,M,"0") :- inp(M,R).
s(R,M,"0") :- out(M,R).
s(R,M,"0") :- reaction(R), metabolite(M), not product(M,R,_), not reactant(M,R,_).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% REGULATIONS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

upBound(T,R,U) :- debug(T), reaction(R), bounds(R,L,U), not inp(_, R).
upBound(T,R,U) :- debug(T), reaction(R), bounds(R,L,U), inp(M, R), obs(T,M,1), not restriction(T,R,_).
upBound(T,R,U) :- debug(T), reaction(R), inp(M, R), obs(T,M,1), restriction(T,R,U).
upBound(T,R,0) :- debug(T), reaction(R), inp(M, R), obs(T,M,-1).

%%%%%%%%%%%%%%%%%%%%
% VARIABLES
%%%%%%%%%%%%%%%%%%%%

%%%%%%%%%%
% PRIMAL
%%%%%%%%%%
&dom(p(T)){L..U} = f(R):- debug(T), reaction(R), bounds(R,L,_), upBound(T,R,U).

%%%%%%%%%%
% DUAL
%%%%%%%%%%
&dom(d(T)){ "0.0".."1.0"} = d(R) :- debug(T), reaction(R).
&dom(d(T)){"-1.0".."1.0"} = p(M) :- debug(T), metabolite(M).

%%%%%%%%%%%%%%%%%%%%
% ERROR
%%%%%%%%%%%%%%%%%%%%
&sum(p(T)){ primal } >= O*(1-E) :- debug(T), obj(T,O), coeff(E).
&sum(d(T)){ dual } <= O*(1+E) :- debug(T), obj(T,O), coeff(E).

%%%%%%%%%%%%%%%%%%%%
% rFBA - PRIMAL
%%%%%%%%%%%%%%%%%%%%
&sum(p(T)){primal; -f("Growth")} = 0 :- debug(T).
&sum(p(T)){S * f(R): reaction(R), s(R,M,S)} = 0 :- debug(T), metabolite(M).
&sum(p(T)){f(R)} = 0 :- debug(T), reaction(R), node(R), not w_obs(T,R,1).

%%%%%%%%%%%%%%%%%%%%
% rFBA - DUAL
%%%%%%%%%%%%%%%%%%%%
&sum(d(T)){dual; -U * d(R): upBound(T,R,U)} = 0 :- debug(T).
&sum(d(T)){d("Growth"); S * p(M): metabolite(M), s("Growth",M,S), not inp(M,"Growth")} >= 1 :- debug(T).
&sum(d(T)){d(R); S * p(M): metabolite(M), s(R,M,S), not inp(M,R)} >= 0 :- debug(T), reaction(R), R!="Growth", w_obs(T,R,1).
&sum(d(T)){d(R); S * p(M): metabolite(M), s(R,M,S)} >= 0 :- debug(T), reaction(R), R!="Growth", node(R), not w_obs(T,R,-1).

%%%%%%%%%%%%%%%%%%%%
% VALID STATES
%%%%%%%%%%%%%%%%%%%%
&dom(v(T)){L..U} = f(R):- debug(T), reaction(R), bounds(R,L,_), upBound(T,R,U).

&sum(v(T)){S * f(R): reaction(R), s(R,M,S)} = 0 :- debug(T), metabolite(M).

used_node(R) :- reaction(R), clause(_, _, R, _).
&sum(v(TO)){f(R)} = 0 :- debug(TO), reaction(R), tlink(TO, TM), used_node(R), v(TM, R, -1).
&sum(v(TO)){f(R)} >= E :- debug(TO), reaction(R), tlink(TO, TM),  used_node(R), v(TM, R, 1), epsilon(E).